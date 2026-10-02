import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

class Error(Exception):
    def __init__(self,message,status): self.status=status;super().__init__(message)

@pytest.fixture
def resolver():
    source=Path('app/controllers/cafe_wallet_controller.py').read_text()
    fn=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='resolve_qr')
    signer=URLSafeTimedSerializer('test',salt='cafe-pc-qr-v1')
    link=SimpleNamespace(status='active')
    db=SimpleNamespace(session=SimpleNamespace(get=Mock(return_value=link)))
    scope=dict(signer=lambda:signer,CafeError=Error,BadSignature=BadSignature,SignatureExpired=SignatureExpired,db=db,ConsoleLinkSession=object)
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'qr','exec'),scope)
    return scope['resolve_qr'],signer,link,db

def test_raw_token_and_checkout_url_resolve_same_link(resolver):
    resolve,signer,link,_=resolver
    token=signer.dumps({'link_id':1})
    assert resolve(token) is link
    assert resolve('https://checkout.example/?qr='+token) is link

@pytest.mark.parametrize('value',[None,{},'', 'https://example/?console_id=1','https://example/?qr=a&qr=b','tampered'])
def test_bad_input_never_resolves_device(resolver,value):
    resolve,_,_,db=resolver
    with pytest.raises(Error): resolve(value)
    db.session.get.assert_not_called()
