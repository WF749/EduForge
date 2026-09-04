"""带退避的重试工具。"""

import time
from typing import Callable, Tuple, Type


def with_retry(
    fn: Callable[[], "T"],
    *,
    retries: int = 2,
    base_delay: float = 1.0,
    backoff: float = 2.0,
    retry_on: Tuple[Type[BaseException], ...] = (Exception,),
) -> "T":
    """执行 fn，遇到 retry_on 中的异常时按指数退避重试，最多 retries 次。

    全部失败后抛出最后一次的异常。
    """
    last: BaseException | None = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except retry_on as e:  # type: ignore[misc]
            last = e
            if attempt < retries:
                time.sleep(base_delay * (backoff ** attempt))
    assert last is not None
    raise last
