import asyncio
from json import loads
from random import choice
from sys import stderr
from threading import Thread, active_count

import aiofiles
import aiohttp
import aiohttp_proxy
from eth_account.messages import encode_defunct
from loguru import logger
from pyuseragents import random as random_useragent
from web3.auto import w3

logger.remove()
logger.add(stderr, format="<white>{time:HH:mm:ss}</white>"
                          " | <level>{level: <8}</level>"
                          " | <cyan>{line}</cyan>"
                          " - <white>{message}</white>")

headers = {
    'accept': '*/*',
    'accept-language': 'ru,en;q=0.9,vi;q=0.8,es;q=0.7,cy;q=0.6',
    'content-type': 'application/json'
}


def create_wallet() -> tuple[str, str]:
    account = w3.eth.account.create()
    private_key = str(account.privateKey.hex())
    address = str(w3.toChecksumAddress(account.address))

    return address, private_key


async def get_connector() -> aiohttp_proxy.connector.ProxyConnector | None:
    connector = None

    if proxy_list:
        connector = aiohttp_proxy.ProxyConnector.from_url(choice(proxy_list))

    return connector


class Main:
    @staticmethod
    async def get_uuid(session: aiohttp.client.ClientSession) -> str:
        r = await session.get('https://www.dimensionals.com/whitelistapi/authentication')
        local_uuid = loads(await r.text())['data']['uuid']

        return local_uuid

    @staticmethod
    def get_sign_hash(private_key: str,
                      local_uuid: str) -> str:
        sign = w3.eth.account.sign_message(encode_defunct(text=local_uuid),
                                           private_key=private_key).signature.hex()
        return sign

    @staticmethod
    async def send_signed_hash(session: aiohttp.client.ClientSession,
                               wallet_address: str,
                               sign_hash: str) -> bool:
        r = await session.post('https://www.dimensionals.com/whitelistapi/eve',
                               json={
                                   'publicAddress': wallet_address
                               })

        if loads(await r.text())['status'] != 'success':
            logger.error(f'{wallet_address} | Wrong Response, text: {await r.text()}')
            return False

        r = await session.post('https://www.dimensionals.com/whitelistapi/authentication',
                               json={
                                   'sign': sign_hash
                               })

        if loads(await r.text())['status'] == 'success':
            return True

        logger.error(f'{wallet_address} | Wrong Response, text: {await r.text()}')
        return False

    @staticmethod
    async def complete_registration(session: aiohttp.client.ClientSession,
                                    wallet_address: str) -> bool:
        r = await session.post('https://www.dimensionals.com/whitelistapi/eve/finishRegistration',
                               json={
                                   'address': wallet_address,
                                   "answers": [
                                       {
                                           "question": "What is your favorite role playing game?",
                                           "answer": choice(roles_list)
                                       },
                                       {
                                           "question": "What is your favorite tv show franchise?",
                                           "answer": choice(franchises_list)
                                       },
                                       {
                                           "question": "Which streamers do you watch the most?",
                                           "answer": choice(streamers_list)
                                       }
                                   ]
                               })

        if loads(await r.text())['status'] == 'success':
            return True

        logger.error(f'{wallet_address} | Wrong Response, text: {await r.text()}')
        return False

    async def main_work(self,
                        private_key: str,
                        wallet_address: str) -> None:
        async with aiohttp.ClientSession(headers={
            **headers,
            'user-agent': random_useragent()
        },
                connector=await get_connector()) as session:
            local_uuid = await self.get_uuid(session=session)
            sign_hash = self.get_sign_hash(private_key=private_key,
                                           local_uuid=local_uuid)

            send_signed_hash_result = await self.send_signed_hash(session=session,
                                                                  wallet_address=wallet_address,
                                                                  sign_hash=sign_hash)

            if not send_signed_hash_result:
                return

            complete_registration_result = await self.complete_registration(session=session,
                                                                            wallet_address=wallet_address)

            if not complete_registration_result:
                return

            async with aiofiles.open('registered.txt', 'a', encoding='utf-8-sig') as f:
                await f.write(f'{private_key}:{wallet_address}\n')

            logger.success(f'{wallet_address} | Successfully registered')


def wrapper():
    local_address, local_private_key = create_wallet()

    asyncio.run(Main().main_work(private_key=local_private_key,
                                 wallet_address=local_address))


if __name__ == '__main__':
    proxy_list = None

    with open('role_playing_game.txt', 'r', encoding='utf-8-sig') as file:
        roles_list = [row.strip() for row in file]

    with open('tv_show_franchise.txt', 'r', encoding='utf-8-sig') as file:
        franchises_list = [row.strip() for row in file]

    with open('streamers.txt', 'r', encoding='utf-8-sig') as file:
        streamers_list = [row.strip() for row in file]

    threads = int(input('Threads: '))
    use_proxies = input('Use Proxy? (y/N): ').lower()

    if use_proxies == 'y':
        proxy_folder = input('Drop .txt with proxies (type://user:pass@ip:port or type://ip:port): ')

        with open(proxy_folder, 'r', encoding='utf-8-sig') as file:
            proxy_list = [row.strip() for row in file]

    print('')

    while True:
        if active_count() - 1 < threads:
            Thread(target=wrapper).start()
