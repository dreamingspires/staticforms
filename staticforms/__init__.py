import asyncio
from starlette.datastructures import FormData
from fastapi import APIRouter, FastAPI, HTTPException, Request
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, HttpUrl, PrivateAttr
from typing import Any, Awaitable, Callable, Dict, List, Optional


class BackendConfig(BaseModel):
    # TODO: private attr for type?
    _type: str
    pass


class EmailConfig(BackendConfig):
    _type = PrivateAttr('email')
    subject: str
    replyTo: List[EmailStr]
    redirectTo: HttpUrl


class FormPrinterModel(BaseModel):
    custom_message: str


async def form_printer(config: FormPrinterModel, form_data: FormData):
    print(config.custom_message)
    print(form_data)


async def error_backend(form_data: FormData):
    raise ValueError('test')


class TokenModel(BaseModel):
    backends: List[BackendConfig]
    custom: Dict[str, Any]


def generate(
        prefix: str = '',
        tags: List[str] = ['staticforms'],
        secret_key: Optional[str] = None,
        algorithm: str = 'HS256',
        backends: List[Callable[[BackendConfig, FormData],
                                Awaitable[None]]] = [],
        verify: Callable[[TokenModel], None] = lambda x: None):

    allowed_backends = {backend.__name__: backend for backend in backends}

    router = APIRouter(
        prefix=prefix,
        tags=tags
    )

    @router.post('/submit')
    async def submit(token: str, request: Request):
        payload = TokenModel(**jwt.decode(token, secret_key, algorithm))
        try:
            verify(payload)
        except Exception as e:
            raise HTTPException(status_code=500,
                                detail=f'verify failed with {e}')
        form_data = await request.form()
        results = await asyncio.gather(
                    *map(lambda x: x(form_data), allowed_backends.values()),
                    return_exceptions=True)
        exceptions = {list(allowed_backends.keys())[i]: repr(r)
                      for i, r in enumerate(results)
                      if isinstance(r, Exception)}
        if exceptions:
            raise HTTPException(status_code=500, detail=exceptions)
        return None

    return router


router = generate(backends=[form_printer, error_backend])
app = FastAPI()
app.include_router(router)
