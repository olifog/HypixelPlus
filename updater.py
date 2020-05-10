import asyncio
import aiohttp
import motor.motor_asyncio
import json
from extras.hypixel import HypixelAPI
from datetime import datetime
from extras.requesthandler import RequestHandler
import time
from operator import itemgetter
from pytz import timezone


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
        async for g in self.db.guilds.find({"updating": {"$ne": True}}).sort([("lastModifiedData", 1)]).limit(1):
            oldest = g

        if oldest is None:
            return

        start = time.time()

        await self.db.guilds.update_one({'_id': oldest['_id']}, {'$set': {'updating': True}})

        try:
            guild = await self.hypixelapi.getGuild(id=oldest['guildid'])
            update = {
                "guildid": guild.JSON['_id'],
                "name": guild.JSON['name'],
                "timeCreated": datetime.fromtimestamp(float(guild.JSON['created']) / 1000),
                "exp": guild.JSON['exp'],
                "level": await self.guild_exp_to_level(int(guild.JSON['exp'])),
                "tag": guild.JSON['tag'],
                "description": guild.JSON['description'],
                "tagColor": guild.JSON['tagColor'],
                "guildExpByGameType": guild.JSON['guildExpByGameType'],
                "preferredGames": guild.JSON['preferredGames'],
                "updating": False
            }

            sorted_ranks = sorted(guild.JSON['ranks'], key=itemgetter('priority'))
            update['ranks'] = [{'name': 'Guild Master', 'tag': 'GM', 'default': False}]

            tags = {'Guild Master': 'GM'}

            for x in range(len(sorted_ranks)):
                rank = sorted_ranks[x]
                tags[rank['name']] = rank['tag']

                try:
                    if oldest['ranks'][x] != rank:
                        raise KeyError
                except KeyError:
                    pass

                update['ranks'].append({'name': rank['name'], 'tag': rank['tag'], 'default': rank['default']})

            todayExp = []
            today = datetime.now(tz=self.est).strftime("%Y-%m-%d")
            memberlist = []

            update['members'] = []
            for member in guild.JSON['members']:
                data = {'uuid': member['uuid'], 'joined': datetime.fromtimestamp(float(member['joined']) / 1000)}
                memberlist.append(member['uuid'])

                dbplayer = await self.db.players.find_one({'uuid': member['uuid']})

                try:
                    data['name'] = dbplayer['displayname']
                    pupdate = {'guildid': guild.JSON['_id'], 'guildRank': member['rank'], 'guildTag': tags[member['rank']]}

                    for gdata in pupdate:
                        await self.db.players.update_one({'_id': dbplayer['_id']}, {'$set': pupdate})
                        break
                except (KeyError, TypeError):
                    get_from_api = True
                    try:
                        for old_mem in oldest['members']:
                            if old_mem['uuid'] == member['uuid']:
                                try:
                                    data['name'] = old_mem['name']
                                    get_from_api = False
                                except KeyError:
                                    pass
                                break
                    except KeyError:
                        pass

                    if get_from_api:
                        url = 'https://playerdb.co/api/player/minecraft/' + member['uuid']
                        resp = await self.handler.getJSON(url)
                        data['name'] = resp['data']['player']['username']

                try:
                    todayExp.append([data['name'], member['expHistory'][today]])
                except KeyError:
                    todayExp.append([data['name'], 0])

                newExpHistory = member['expHistory']
                newExpHistory['week'] = sum(newExpHistory.values())

                data['expHistory'] = newExpHistory
                update['members'].append(data)

            topTodayExp = sorted(todayExp, key=itemgetter(1), reverse=True)[:10]
            update['top'] = topTodayExp

            async for player in self.db.players.find({'guildid': guild.JSON['_id']}):
                if player['uuid'] not in memberlist:
                    unset = {'guildid': '', 'guildRank': '', 'guildRankTag': ''}
                    await self.db.players.update_one({'_id': player['_id']}, {'$unset': unset})

            update["lastModifiedData"] = datetime.utcnow()

            await self.db.guilds.update_one({'_id': oldest['_id']}, {'$set': update})

        except Exception as e:
            print(e)
            await self.db.guilds.update_one({'_id': oldest['_id']}, {'$set': {'updating': False}})

    async def update_player(self):
        oldest = None
        async for player in self.db.players.find({"updating": {"$ne": True}}).sort([("lastModifiedData", 1)]).limit(1):
            oldest = player

        await self.db.players.update_one({'_id': oldest['_id']}, {'$set': {'updating': True}})

        player = await self.hypixelapi.getPlayer(uuid=oldest['uuid'])

        update = {
            "level": player.getLevel(),
            "hypixelRank": player.getRank(),
            "updating": False
        }

        needed_data = ['displayname', 'karma', 'firstLogin', 'lastLogin']
        for d in needed_data:
            try:
                update[d] = player.JSON[d]
            except KeyError:
                pass

        try:
            update['online'] = player.JSON['lastLogout'] < player.JSON['lastLogin']
        except KeyError:
            pass

        try:
            update['discordName'] = player.JSON['socialMedia']['links']['DISCORD']
        except KeyError:
            pass

        update['lastModifiedData'] = datetime.utcnow()

        await self.db.players.update_one({'_id': oldest['_id']}, {'$set': update})


    async def updater(self):
        await asyncio.sleep(0.55)
        asyncio.create_task(self.updater())
        self.iterations += 1

        if self.iterations % 10 == 0:
            await self.update_guild()
        else:
            await self.update_player()

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
