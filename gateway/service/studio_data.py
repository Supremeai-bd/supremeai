"""Narrow PostgREST adapter for the deployed Studio gateway (no core ORM in its image).

Only server-selected tables/columns/filters. Never forward a browser's query string,
return a service credential, or substitute an empty result for a failed query.
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .keygen import verify_key


def account_id(request: Request) -> str:
    """Wallet records belong to a registered account, not a guest or shared API key.
    Delegates to unified resolve_user_id with require_registered=True.
    """
    try:
        from .auth_identity import resolve_user_id
    except ImportError:
        try:
            from gateway.service.auth_identity import resolve_user_id  # type: ignore[no-redef]
        except ImportError:
            from service.auth_identity import resolve_user_id  # type: ignore[no-redef]
    return resolve_user_id(request, require_registered=True)


async def _rows(method: str, table: Literal['customers', 'user_wallets', 'transaction_ledger', 'platform_settings'],
                params: dict[str, str], body: dict | None = None) -> list[dict]:
    url = os.getenv('SUPABASE_URL', '').strip().rstrip('/')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '').strip()
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.path or parsed.query or parsed.fragment or not key:
        raise HTTPException(503, 'Studio database is not configured on the gateway.')
    headers = {'apikey': key, 'Authorization': f'Bearer {key}', 'Accept': 'application/json'}
    if method != 'GET':
        headers['Prefer'] = 'return=representation'
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8, connect=3), follow_redirects=False) as client:
            res = await client.request(method, f'{url}/rest/v1/{table}', params=params, headers=headers, json=body)
        if res.status_code == 409:
            raise HTTPException(409, 'A conflicting Studio record already exists.')
        res.raise_for_status()
        rows = res.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, 'Studio database request failed.') from None
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise HTTPException(502, 'Invalid Studio database response.')
    return rows


def _first(rows: list[dict], what: str) -> dict:
    if not rows:
        raise HTTPException(404, f'{what} not found.')
    return rows[0]


# Mirrors the columns of the cust_dir_0001 migration. Privilege assignments are
# NOT customer metadata; an unsupported RBAC change must not appear to succeed.
class CustomerFields(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(pattern=r'^\S+@\S+\.\S+$', max_length=255)
    tier: Literal['Free', 'Pro', 'Enterprise'] = 'Free'
    status: Literal['active', 'past_due', 'suspended'] = 'active'
    mrr: float = Field(default=0, ge=0, allow_inf_nan=False)
    tokens_used: int = Field(default=0, ge=0, alias='tokensUsed')
    token_limit: int = Field(default=100000, ge=0, alias='tokenLimit')
    connected_repos: int = Field(default=0, ge=0, alias='connectedRepos')
    github_handle: str | None = Field(default=None, alias='githubHandle', max_length=255)
    region: str | None = Field(default=None, max_length=100)
    is_developer_eligible: bool = Field(default=False, alias='isDeveloperEligible')


_CUSTOMER_SELECT = ','.join([
    'id', 'joinedDate:joined_date', 'lastActive:last_active',
    *(f'{f.alias}:{name}' if f.alias else name for name, f in CustomerFields.model_fields.items()),
])


async def customers(cid: str | None = None) -> list[dict]:
    params = {'select': _CUSTOMER_SELECT, 'order': 'id.asc'}
    if cid is not None:
        return await _rows('GET', 'customers', {**params, 'id': f'eq.{cid}'})
    # PostgREST caps page size. A list must not silently truncate the directory.
    result: list[dict] = []
    while True:
        page = await _rows('GET', 'customers', {**params, 'limit': '250', 'offset': str(len(result))})
        result.extend(page)
        if len(page) < 250:
            return result


async def create_customer(body: CustomerFields) -> dict:
    now = datetime.now(timezone.utc)
    payload = {**body.model_dump(), 'email': body.email.lower(), 'id': str(uuid.uuid4()),
               'joined_date': now.date().isoformat(), 'last_active': now.isoformat()}
    rows = await _rows('POST', 'customers', {'select': _CUSTOMER_SELECT}, payload)
    if not rows:
        raise HTTPException(502, 'Database did not confirm customer creation.')
    return rows[0]


async def update_customer(cid: str, patch: dict) -> dict:
    current = _first(await customers(cid), 'Customer')
    fields = {f.alias or name for name, f in CustomerFields.model_fields.items()}
    try:
        validated = CustomerFields.model_validate({**{k: v for k, v in current.items() if k in fields}, **patch})
    except ValidationError:
        raise HTTPException(422, 'Invalid or unsupported customer fields.') from None
    values = validated.model_dump(include={k for k, f in CustomerFields.model_fields.items() if (f.alias or k) in patch})
    if not values:
        raise HTTPException(422, 'No customer updates supplied.')
    if 'email' in values:
        values['email'] = validated.email.lower()
    values['updated_at'] = datetime.now(timezone.utc).isoformat()
    return _first(await _rows('PATCH', 'customers', {'id': f'eq.{cid}', 'select': _CUSTOMER_SELECT}, values), 'Customer')


async def delete_customer(cid: str) -> None:
    _first(await _rows('DELETE', 'customers', {'id': f'eq.{cid}', 'select': 'id'}), 'Customer')


async def wallet(uid: str) -> dict:
    rows = await _rows('GET', 'user_wallets', {'select': 'user_id,balance_usd,monthly_allowance_usd', 'user_id': f'eq.{uid}', 'limit': '1'})
    return _first(rows, 'Wallet')


async def invoices(uid: str) -> dict:
    # Only settled top-ups become receipts. Usage debits are not paid invoices.
    params = {'select': 'transaction_id,amount_usd,timestamp,description', 'user_id': f'eq.{uid}',
              'transaction_type': 'in.(stripe_topup,topup)', 'order': 'timestamp.desc,transaction_id.asc'}
    receipts = []
    while True:
        page = await _rows('GET', 'transaction_ledger', {**params, 'limit': '250', 'offset': str(len(receipts))})
        receipts.extend({'id': r['transaction_id'], 'invoiceNumber': r['transaction_id'], 'amountUsd': float(r['amount_usd']),
                         'date': r['timestamp'], 'planName': r.get('description') or 'Account credit', 'status': 'paid'} for r in page)
        if len(page) < 250:
            return {'invoices': receipts, 'history': receipts}


class Banner(BaseModel):
    active: bool
    message: str
    level: Literal['info', 'warning', 'critical']


class ModelPolicy(BaseModel):
    enabled: bool
    minTier: Literal['Free', 'Pro', 'Enterprise']


class PlatformConfig(BaseModel):
    """Public projection only; never return the raw global row (includes security settings)."""
    maintenanceMode: bool
    maintenanceMessage: str
    announcementBanner: Banner
    allowNewSignups: bool
    defaultModelId: str
    featureFlags: dict[str, bool]
    modelPolicies: dict[str, ModelPolicy]


async def platform_state() -> tuple[dict, dict, str]:
    rows = await _rows('GET', 'platform_settings', {'select': 'value,updated_at', 'id': 'eq.global', 'limit': '1'})
    if not rows:
        raise HTTPException(503, 'Studio platform settings have not been provisioned.')
    try:
        value = rows[0]['value']
        config = PlatformConfig.model_validate({**value['platformConfig'], 'featureFlags': value['runtimeFeatureFlags']})
        return config.model_dump(), value, rows[0]['updated_at']
    except (KeyError, TypeError, ValidationError):
        raise HTTPException(502, 'Invalid Studio platform settings.') from None


async def change_platform(*, settings: dict | None = None, flag: dict | None = None, policy: dict | None = None) -> dict:
    config, raw, revision = await platform_state()
    if settings is not None:
        patch = {k: v for k, v in settings.items() if k != 'actor'}
        if not patch or patch.keys() - {'maintenanceMode', 'maintenanceMessage', 'announcementBanner', 'allowNewSignups', 'defaultModelId'}:
            raise HTTPException(422, 'Invalid platform settings update.')
        if 'defaultModelId' in patch and (not isinstance(patch['defaultModelId'], str) or patch['defaultModelId'] not in config['modelPolicies']):
            raise HTTPException(422, 'Unknown default model.')
        if isinstance(patch.get('announcementBanner'), dict):
            patch['announcementBanner'] = {**config['announcementBanner'], **patch['announcementBanner']}
        config.update(patch)
        config['featureFlags']['maintenance_mode'] = config['maintenanceMode']
    elif flag is not None:
        name = flag.get('name')
        if not isinstance(name, str) or name not in config['featureFlags'] or not isinstance(flag.get('enabled'), bool):
            raise HTTPException(422, 'Unknown flag or invalid enabled value.')
        config['featureFlags'][name] = flag['enabled']
        if name == 'maintenance_mode':
            config['maintenanceMode'] = flag['enabled']
    elif policy is not None:
        model = policy.get('modelId')
        if not isinstance(model, str) or model not in config['modelPolicies'] or not ({'enabled', 'minTier'} & policy.keys()):
            raise HTTPException(422, 'Unknown model or missing policy.')
        config['modelPolicies'][model].update({k: policy[k] for k in ('enabled', 'minTier') if k in policy})
    try:
        config = PlatformConfig.model_validate(config, strict=True).model_dump()
    except ValidationError:
        raise HTTPException(422, 'Invalid Studio configuration.') from None
    if not revision:
        raise HTTPException(503, 'Studio settings lack a revision timestamp.')
    value = {**raw, 'runtimeFeatureFlags': config['featureFlags'],
             'platformConfig': {**raw['platformConfig'], **{k: v for k, v in config.items() if k != 'featureFlags'}}}
    saved = await _rows('PATCH', 'platform_settings', {'id': 'eq.global', 'updated_at': f'eq.{revision}', 'select': 'id'},
                        {'value': value, 'updated_at': datetime.now(timezone.utc).isoformat()})
    if not saved:
        raise HTTPException(409, 'Studio settings changed concurrently. Refresh and try again.')
    return config
