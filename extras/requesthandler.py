
import aiohttp
from io import BytesIO
import discord
import json


class RequestHandler:
    def __init__(self, loop):
        self.loop = loop
        self.session = None

    async def close(self):
        await self.session.close()

    async def get(self, url):
        if self.session is None:
            self.session = aiohttp.ClientSession(loop=self.loop)

        async with self.session.get(url) as r:
            await r.read()

        return r

    async def getJSON(self, url):
        resp = await self.get(url)
        return await resp.json()

    async def getPic(self, url, filename='picture.png'):
        resp = await self.get(url)
        return discord.File(BytesIO(resp._body), filename=filename)
