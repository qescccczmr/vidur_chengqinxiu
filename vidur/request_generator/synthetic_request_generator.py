from typing import List

from vidur.config import SyntheticRequestGeneratorConfig
from vidur.entities import Request
from vidur.request_generator.base_request_generator import BaseRequestGenerator
from vidur.request_generator.request_interval_generator_registry import (
    RequestIntervalGeneratorRegistry,
)
from vidur.request_generator.request_length_generator_registry import (
    RequestLengthGeneratorRegistry,
)
from vidur.types import RequestIntervalGeneratorType
from vidur.utils.random import set_seeds


class SyntheticRequestGenerator(BaseRequestGenerator):

    def __init__(self, config: SyntheticRequestGeneratorConfig):
        super().__init__(config)

        self.request_length_generator = RequestLengthGeneratorRegistry.get(
            self.config.length_generator_config.get_type(),
            self.config.length_generator_config,
        )
        self.request_interval_generator = RequestIntervalGeneratorRegistry.get(
            self.config.interval_generator_config.get_type(),
            self.config.interval_generator_config,
        )

    def _generate_next_request(self, last_arrived_at: float) -> Request:
        inter_request_time = (
            self.request_interval_generator.get_next_inter_request_time()
        )
        if inter_request_time is None:
            return None
        arrived_at = last_arrived_at + inter_request_time

        (
            prefill_tokens,
            decode_tokens,
        ) = self.request_length_generator.get_next_num_tokens()

        if prefill_tokens is None or decode_tokens is None:
            return None

        return Request(
            arrived_at=arrived_at,
            num_prefill_tokens=int(prefill_tokens),
            num_decode_tokens=int(decode_tokens),
        )

    def _generate_requests(self) -> List[Request]:
        requests = []

        current_time = 0

        # first priority is duration
        if self.config.duration is not None:
            while current_time < self.config.duration:
                request = self._generate_next_request(current_time)
                current_time = request.arrived_at
                requests.append(request)
        elif self.config.num_requests is not None:
            for _ in range(self.config.num_requests):
                request = self._generate_next_request(current_time)
                current_time = request.arrived_at
                requests.append(request)
        else:
            assert (
                self.config.interval_generator_config.get_type()
                == RequestIntervalGeneratorType.TRACE
            )

            while True:
                request = self._generate_next_request(current_time)
                if request is None:
                    break
                current_time = request.arrived_at
                requests.append(request)

        return requests

    def generate_requests(self) -> List[Request]:
        assert (
            self.config.duration
            or self.config.num_requests
            or self.config.interval_generator_config.get_type()
            == RequestIntervalGeneratorType.TRACE
        )

        set_seeds(self.config.seed)

        requests = self._generate_requests()

        # sort requests by arrival time
        requests.sort(key=lambda x: x.arrived_at)
        # remove any requests that arrived after the time limit
        if self.config.duration is not None:
            requests = [
                request
                for request in requests
                if request.arrived_at < self.config.duration
            ]

        return requests


from vidur.config import SyntheticRequestGeneratorConfig
from vidur.config.config import FixedRequestLengthGeneratorConfig
from vidur.config.config import PoissonRequestIntervalGeneratorConfig
# 配置请求长度生成器，假设请求长度为固定值
length_config = FixedRequestLengthGeneratorConfig(
    prefill_tokens=2048,
    decode_tokens=512,
)

# 配置请求间隔生成器，使用 Poisson 分布生成请求间隔
interval_config = PoissonRequestIntervalGeneratorConfig(qps=0.5)

# 配置合成请求生成器
config = SyntheticRequestGeneratorConfig(
    seed=42,
    length_generator_config=length_config,
    interval_generator_config=interval_config,
    num_requests=10,  # 生成 10 个请求
)

# 创建合成请求生成器实例
synthetic_request_generator = SyntheticRequestGenerator(config)

# 生成请求
requests = synthetic_request_generator.generate_requests()
print(synthetic_request_generator.request_length_generator)

# 打印生成的请求
for request in requests:
    print(f"Request arrived at {request.arrived_at} with {request.num_prefill_tokens} prefill tokens and {request.num_decode_tokens} decode tokens.")