class BusinessError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


def require(condition, detail: str, status: int = 400):
    if not condition:
        raise BusinessError(status, detail)
