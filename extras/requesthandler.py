from io import BytesIO

import aiohttp
import discord
from aiohttp import ClientOSError


class RequestHandler:
    def __init__(self, loop):
        self.loop = loop
        self.session = None

    async def close(self):
        await self.session.close()

    async def get(self, url):
        if self.session is None:
            self.session = aiohttp.ClientSession(loop=self.loop)

        tries = 0

        while tries < 10:
            try:
                async with self.session.get(url) as r:
                    await r.read()
                    return r
            except (ConnectionResetError, ClientOSError):
                tries += 1

        return None

    async def getJSON(self, url):
        resp = await self.get(url)
        return await resp.json()

    async def getPic(self, url, filename='picture.png'):
        resp = await self.get(url)
        return discord.File(BytesIO(resp._body), filename=filename)
