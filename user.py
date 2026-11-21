# coding: utf-8
import uuid
import hashlib
import base64
from urllib.parse import quote_plus
import fgourl
import mytime
import rsa
import requests
from bonus_actions import friend_pool, ticket_orders


class ParameterBuilder:
    def __init__(self, uid: str, auth_key: str, secret_key: str):
        self.uid_ = uid
        self.auth_key_ = auth_key
        self.secret_key_ = secret_key
        self.content_ = ''
        self.parameter_list_ = [
            ('appVer', fgourl.app_ver_),
            ('authKey', self.auth_key_),
            ('dataVer', str(fgourl.data_ver_)),
            ('dateVer', str(fgourl.date_ver_)),
            ('idempotencyKey', str(uuid.uuid4())),
            ('lastAccessTime', str(mytime.GetTimeStamp())),
            ('userId', self.uid_),
            ('verCode', fgourl.ver_code_),
        ]

    def AddParameter(self, key: str, value: str):
        self.parameter_list_.append((key, value))

    def Build(self) -> str:
        self.parameter_list_.sort(key=lambda tup: tup[0])
        temp = ''
        for first, second in self.parameter_list_:
            if temp:
                temp += '&'
                self.content_ += '&'
            escaped_key = quote_plus(first)
            if not second:
                temp += first + '='
                self.content_ += escaped_key + '='
            else:
                escaped_value = quote_plus(second)
                temp += first + '=' + second
                self.content_ += escaped_key + '=' + escaped_value

        temp += ':' + self.secret_key_
        self.content_ += '&authCode=' + quote_plus(base64.b64encode(hashlib.sha1(temp.encode('utf-8')).digest()))
        return self.content_

    def Clean(self):
        self.content_ = ''
        self.parameter_list_ = [
            ('appVer', fgourl.app_ver_),
            ('authKey', self.auth_key_),
            ('dataVer', str(fgourl.data_ver_)),
            ('dateVer', str(fgourl.date_ver_)),
            ('idempotencyKey', str(uuid.uuid4())),
            ('lastAccessTime', str(mytime.GetTimeStamp())),
            ('userId', self.uid_),
            ('verCode', fgourl.ver_code_),
        ]


class user:
    def __init__(self, user_id: str, auth_key: str, secret_key: str):
        self.name_ = ''
        self.user_id_ = (int)(user_id)
        self.s_ = fgourl.NewSession()
        self.builder_ = ParameterBuilder(user_id, auth_key, secret_key)

    def Post(self, url):
        res = fgourl.PostReq(self.s_, url, self.builder_.Build())
        self.builder_.Clean()
        return res

    def topLogin(self):
        idempotencyKey = self.builder_.parameter_list_[4][1]
        idempotencyKeySignature = rsa.sign(f'{self.user_id_}{idempotencyKey}')
        lastAccessTime = self.builder_.parameter_list_[5][1]
        userState = (-int(lastAccessTime) >> 2) ^ self.user_id_ & fgourl.data_server_folder_crc_

        self.builder_.AddParameter('idempotencyKeySignature', idempotencyKeySignature)
        self.builder_.AddParameter('assetbundleFolder', fgourl.asset_bundle_folder_)
        self.builder_.AddParameter('isTerminalLogin', '1')
        self.builder_.AddParameter('userState', str(userState))
        data = self.Post(f'{fgourl.server_addr_}/login/top?_userId={self.user_id_}')
        self.login_data_ = data

        self.name_ = hashlib.md5(data['cache']['replaced']['userGame'][0]['name'].encode('utf-8')).hexdigest()
        stone = data['cache']['replaced']['userGame'][0]['stone']
        lv = data['cache']['replaced']['userGame'][0]['lv']
        ticket = 0

        # 呼符
        for item in data['cache']['replaced']['userItem']:
            if item['itemId'] == 4001:
                ticket = item['num']
                break

        # 登陆天数
        login_days = data['cache']['updated']['userLogin'][0]['seqLoginCount']
        total_days = data['cache']['updated']['userLogin'][0]['totalLoginCount']
        res = (f'FGO 登录 - JP\n'
               f'账号标识: {self.name_}\n'
               f'连续/累计登录: {login_days}/{total_days} 天\n'
               f'等级: {lv} | 圣晶石: {stone} | 呼符: {ticket}\n')
        counts = {int(item['itemId']): int(item['num']) for item in data['cache']['replaced']['userItem']}
        res += (f'金/银/铜/青铜苹果: {counts.get(100, 0)}/{counts.get(101, 0)}/'
                f'{counts.get(102, 0)}/{counts.get(104, 0)}\n'
                f'青銅の苗木: {counts.get(103, 0)}\n')

        # AP保存：每消耗40 AP兑换1个青銅の果実，仅使用青銅の苗木(itemId=103)
        game = data['cache']['replaced']['userGame'][0]
        act_max = int(game['actMax'])
        act_recover_at = int(game['actRecoverAt'])
        server_time = int(data['cache'].get('serverTime', mytime.GetTimeStamp()))
        ap_until_full = max(0, act_recover_at - server_time)
        now_act = max(0, min(act_max, int(act_max - ap_until_full / 300)))
        saplings = sum(int(item['num']) for item in data['cache']['replaced']['userItem']
                       if int(item['itemId']) == 103)
        apple_num = min(now_act // 40, saplings)
        stored_apples = 0
        if apple_num > 0:
            try:
                self.builder_.AddParameter('id', '13000000')
                self.builder_.AddParameter('num', str(apple_num))
                self.builder_.AddParameter('dayKey', '0')
                purchase = self.Post(f'{fgourl.server_addr_}/shop/purchase?_userId={self.user_id_}')
                confirmed = purchase['response'][0]['success']
                if confirmed.get('purchaseName') != '青銅の果実' or int(confirmed.get('purchaseNum', -1)) != apple_num:
                    raise ValueError('青铜苹果兑换响应与请求不一致')
                stored_apples = apple_num
                now_act -= stored_apples * 40
                print(f'AP存储成功: 青銅の果実 {stored_apples}个')
            except Exception as ex:
                print(f'AP存储失败: {ex}')
        res += f'AP: {now_act}/{act_max} | 本次存青铜苹果: {stored_apples}\n'

        # 友情点
        add_fp = data['response'][0]['success']['addFriendPoint']
        total_fp = data['cache']['replaced']['tblUserGame'][0]['friendPoint']
        res += f'友情点: {total_fp} (本次 +{add_fp})\n'

        login_success = data['response'][0]['success']
        bonuses = login_success.get('seqLoginBonus', [])
        if bonuses:
            bonus = bonuses[0]
            res += f'登录奖励: {bonus.get("message", "")}\n'
            for item in bonus.get('items', []):
                res += f'  {item["name"]} x{item["num"]}\n'
        campaigns = login_success.get('campaignbonus', [])
        if campaigns:
            campaign = campaigns[0]
            res += f'活动奖励: {campaign.get("name", "")}\n'
            for item in campaign.get('items', []):
                res += f'  {item["name"]} x{item["num"]}\n'
        server_now_time = mytime.TimeStampToString(data['cache']['serverTime'])
        res += f'服务器时间: {server_now_time}\n--------\n'
        print(res)
        return res

    def drawFreeFriendship(self):
        """Try one daily ten-pull, matching F-D-L behavior; no repeat or paid gacha."""
        try:
            catalog = requests.get(
                'https://raw.githubusercontent.com/DNNDHH/GSubList/Main/update.json', timeout=20)
            catalog.raise_for_status()
            sub_id = friend_pool(catalog.json(), int(self.login_data_['cache']['serverTime']))
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return '友情召唤: 卡池数据不可用，跳过\n'
        self.builder_.AddParameter('storyAdjustIds', '[]')
        self.builder_.AddParameter('selectBonusList', '')
        for key, value in (('gachaId', 1), ('gachaSubId', sub_id), ('num', 10),
                           ('ticketItemId', 0), ('shopIdIndex', 1)):
            self.builder_.AddParameter(key, str(value))
        try:
            data = self.Post(f'{fgourl.server_addr_}/gacha/draw?_userId={self.user_id_}')
        except Exception:
            return '友情召唤: 请求失败或当日免费次数已用，未重试\n'
        draw = next((item for item in data['response'] if item.get('nid') == 'gacha'), None)
        if draw is None or draw.get('resCode') != '00':
            return '友情召唤: 结果未确认，未重试\n'
        count = len(draw.get('success', {}).get('gachaInfos', []))
        return f'友情召唤: 十连完成，结果 {count} 项\n'

    def buyTickets(self):
        """Buy available monthly/event tickets with mana prisms, once per listing."""
        try:
            response = requests.get(
                'https://raw.githubusercontent.com/DNNDHH/GSubList/Main/Shopdate.json', timeout=30)
            response.raise_for_status()
            if len(response.content) > 20_000_000:
                return '商店呼符: 商品列表过大，跳过\n'
            cache = self.login_data_['cache']
            shops = cache.get('updated', {}).get('userShop', [])
            game = cache['replaced']['userGame'][0]
            orders = ticket_orders(response.json(), shops, game['mana'], int(cache['serverTime']))
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return '商店呼符: 商品数据不可用，跳过\n'
        if not orders:
            return '商店呼符: 无可兑换项或魔力棱镜不足\n'
        results = []
        for label, shop_id, qty, price in orders:
            self.builder_.AddParameter('id', str(shop_id))
            self.builder_.AddParameter('num', str(qty))
            try:
                data = self.Post(f'{fgourl.server_addr_}/shop/purchase?_userId={self.user_id_}')
                purchase = next((x for x in data['response'] if x.get('nid') == 'purchase'), None)
                success = purchase['success'] if purchase and purchase.get('resCode') == '00' else {}
                if success.get('purchaseName') != '呼符' or int(success.get('purchaseNum', -1)) != qty:
                    raise ValueError('purchase response mismatch')
            except Exception:
                results.append(f'{label}呼符: 未确认成功，停止后续购买\n')
                break
            results.append(f'{label}呼符: +{qty}，魔力棱镜 -{price}\n')
        return ''.join(results)

    def topHome(self):
        self.Post(f'{fgourl.server_addr_}/home/top?_userId={self.user_id_}')
