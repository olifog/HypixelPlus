import asyncio
import copy
import json
import time
import traceback
from datetime import datetime, timedelta
from operator import itemgetter

import aiohttp
import motor.motor_asyncio
from pytz import timezone

from extras.hypixel import HypixelAPI
from extras.requesthandler import RequestHandler


class Updater:
    def __init__(self):
        with open('./data/settings.json') as settings:
            self.settings = json.load(settings)
            settings.close()

        uri = f"mongodb://updater:{self.settings['updater_motor_password']}@51.81.32.153:27017/admin"
        self.motor_client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self.motor_client.hypixelPlusDB
        self.iterations = 0
        self.handler = RequestHandler(asyncio.get_event_loop())
        self.hypixelapi = HypixelAPI(self.settings['updater_api_key'], self.handler)
        self.last_task_time = time.time()
        self.est = timezone("US/Eastern")

    async def log(self, msg):
        timestamp = datetime.now()
        await self.db.logs.insert_one({"log": msg, "timestamp": timestamp})

    async def guild_exp_to_level(self, exp):
        levels = [100000, 150000, 250000, 500000, 750000, 1000000, 1250000, 1500000, 2000000, 2500000, 2500000, 2500000,
                  2500000, 2500000]

        l = 0
        for level in levels:
            if exp < level:
                l += exp / level
                break

            l += 1
            exp -= level

        if exp > 0:
            l += exp / 3000000

        return l

    async def update_guild(self):
        oldest = None
        async for g in self.db.guilds.find(
                {"updating": {"$ne": True}, "guildid": {"$ne": None}, "custom": {"$ne": True}}).sort(
                [("lastModifiedData", 1)]).limit(1):
            oldest = g

        if oldest is None:
            return

        await self.db.guilds.update_one({'_id': oldest['_id']}, {'$set': {'updating': True}})

        update = {
            "discordid": oldest['discordid'],
            "updating": False
        }

        optionals = ["nameFormat", "roles"]

        for opt in optionals:
            ret = oldest.get(opt)
            if ret is not None:
                update[opt] = ret

        gid = oldest.get("guildid")
        guild = await self.hypixelapi.getGuild(id=gid)
        update['guildid'] = gid
        update['guildName'] = guild.JSON['name']

        sorted_ranks = sorted(guild.JSON['ranks'], key=itemgetter('priority'))
        update['guildRanks'] = [{'name': 'Guild Master', 'tag': 'GM', 'default': False}]

        tags = {'Guild Master': 'GM'}

        for x in range(len(sorted_ranks)):
            rank = sorted_ranks[x]
            tags[rank['name']] = rank['tag']
            update['guildRanks'].insert(len(update['guildRanks']) - 1,
                                        {'name': rank['name'], 'tag': rank['tag'], 'default': rank['default']})

        top = {'week': [], 'average': []}
        days = []
        for x in range(7):
            d = (datetime.now(tz=self.est) - timedelta(days=x)).strftime("%Y-%m-%d")
            days.append(d)
            top[d] = []

        memberlist = []

        update['members'] = []
        for member in guild.JSON['members']:
            memberlist.append(member['uuid'])
            dbplayer = await self.db.players.find_one({'uuid': member['uuid']})

            newExpHistory = member['expHistory']
            newExpHistory['week'] = sum(newExpHistory.values())
            newExpHistory['average'] = newExpHistory['week'] / 7
            p = {'xp': 0}

            if dbplayer is not None:
                p['player'] = dbplayer['displayname']
                p['discord'] = dbplayer['discordid']
                pupdate = {'guildid': guild.JSON['_id'], 'guildRank': member['rank'],
                           'guildRankTag': tags[member['rank']], 'guildExp': newExpHistory}
                result = await self.db.players.update_one({'_id': dbplayer['_id']}, {'$set': pupdate})
                if result.modified_count == 1:
                    await self.db.players.update_one({'_id': dbplayer['_id']},
                                                     {'$push': {'urgentUpdate': oldest['discordid']}})
            else:
                get_from_api = True
                try:
                    for old_mem in oldest['members']:
                        if old_mem['uuid'] == member['uuid']:
                            try:
                                p['player'] = old_mem['name']
                                get_from_api = False
                            except KeyError:
                                pass
                            break
                except KeyError:
                    pass

                if get_from_api:
                    url = 'https://playerdb.co/api/player/minecraft/' + member['uuid']
                    resp = await self.handler.getJSON(url)
                    p['player'] = resp['data']['player']['username']

            for timeframe, xp in newExpHistory.items():
                p['xp'] = xp
                try:
                    top[timeframe].append(copy.copy(p))
                except KeyError:
                    pass

            update['members'].append({'name': p['player'], 'uuid': member['uuid']})

        for timeframe in top:
            top[timeframe] = sorted(top[timeframe], key=itemgetter('xp'), reverse=True)[:10]

        update['top'] = top

        async for player in self.db.players.find({'guildid': guild.JSON['_id']}):
            if player['uuid'] not in memberlist:
                unset = {'guildid': '', 'guildRank': '', 'guildRankTag': '', 'guildExp': ''}
                await self.db.players.update_one({'_id': player['_id']}, {'$unset': unset})

        update["lastModifiedData"] = datetime.utcnow()

        await self.db.guilds.update_one({'_id': oldest['_id']}, {'$set': update})

    async def update_player(self):
        oldest = None
        async for player in self.db.players.find({"updating": {"$ne": True}}).sort([("lastModifiedData", 1)]).limit(1):
            oldest = player

        if oldest is None:
            return

        await self.db.players.update_one({'_id': oldest['_id']}, {'$set': {'updating': True}})

        try:
            player = await self.hypixelapi.getPlayer(uuid=oldest['uuid'])

            update = {
                "level": player.getLevel(),
                "hypixelRank": player.getRank(),
                "displayname": player.getName()
            }

            new = False

            for key, data in update.items():
                try:
                    if oldest[key] != data:
                        raise KeyError
                except KeyError:
                    new = True
                    break

            update['urgentUpdate'] = oldest['servers']

            if not new:
                update = {}

            update['updating'] = False
            update['lastModifiedData'] = datetime.utcnow()

            await self.db.players.update_one({'_id': oldest['_id']}, {'$set': update})
        except Exception as e:
            await self.db.players.update_one({'_id': oldest['_id']}, {'$set': {'updating': False}})
            raise e

    async def updater(self):
        await asyncio.sleep(0.55)
        asyncio.create_task(self.updater())
        self.iterations += 1

        try:
            if self.iterations % 10 == 0:
                await self.update_guild()
            else:
                await self.update_player()
        except aiohttp.ContentTypeError:
            pass
        except Exception:
            await self.log(traceback.format_exc())

    async def close(self):
        print('\nClosing request handler...')
        await self.handler.close()

        tasks = [t for t in asyncio.all_tasks() if t is not
                 asyncio.current_task()]
        print('Cancelling tasks')

        [task.cancel() for task in tasks]
        try:
            await asyncio.shield(asyncio.gather(*tasks))
        except asyncio.futures.CancelledError:
            pass

        print('Tasks all cancelled, updating guild data...')

        await self.db.guilds.update_many({}, {"$set": {"updating": False}})
        print('Guild data updated; {\'updating\': False}')
        print('Updating player data...')
        await self.db.players.update_many({}, {"$set": {"updating": False}})
        print('Player data updated; {\'updating\': False}')


updater = Updater()

loop = asyncio.get_event_loop()

loop.create_task(updater.updater())
try:
    print('Starting updater...')
    loop.run_forever()
except KeyboardInterrupt:
    loop.run_until_complete(updater.close())

print('Closing loop...')
loop.close()
print('Shut down')
