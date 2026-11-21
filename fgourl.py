import json
import binascii
import base64
import re
import requests
import mytime
import CatAndMouseGame

requests.urllib3.disable_warnings()
session = requests.Session()
session.verify = False

# ===== Game's parameters =====
app_ver_ = ''
data_ver_ = 0
date_ver_ = 0
ver_code_ = ''
asset_bundle_folder_ = ''
data_server_folder_crc_ = 0
server_addr_ = 'https://game.fate-go.jp'
github_token_ = ''
github_name_ = ''
user_agent_ = 'Dalvik/2.1.0 (Linux; U; Android 11; Pixel 5 Build/RD1A.201105.003.A1)'


# ==== User Info ====
def ReadConf():
    raw_url = f'https://raw.githubusercontent.com/{github_name_}/FGODailyBonusLog/main/cfg.json'
    try:
        response = requests.get(raw_url, timeout=20)
        response.raise_for_status()
        data = response.json()
        print('Read config from public raw URL')
    except (requests.RequestException, ValueError) as raw_error:
        if not github_token_:
            raise Exception(
                f'Could not read public config and GithubToken is not configured: {raw_error}'
            ) from raw_error

        api_url = f'https://api.github.com/repos/{github_name_}/FGODailyBonusLog/contents/cfg.json'
        headers = {
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {github_token_}',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': f'{github_name_}_bot',
        }
        response = requests.get(api_url, headers=headers, params={'ref': 'main'}, timeout=20)
        response.raise_for_status()
        file_data = response.json()
        if file_data.get('encoding') != 'base64' or 'content' not in file_data:
            raise Exception('GitHub Contents API did not return base64 file content')
        data = json.loads(base64.b64decode(file_data['content']).decode('utf-8'))
        print('Read config from GitHub Contents API')

    global app_ver_, data_ver_, date_ver_, asset_bundle_folder_, data_server_folder_crc_
    app_ver_ = data['global']['appVer']
    data_ver_ = data['global']['dataVer']
    date_ver_ = data['global']['dateVer']
    asset_bundle_folder_ = data['global']['assetbundleFolder']
    data_server_folder_crc_ = data['global']['dataServerFolderCrc']


def WriteConf(data):
    UploadFileToRepo('cfg.json', data, 'update config')


def UpdateBundleFolder(assetbundle):
    new_assetbundle = CatAndMouseGame.MouseInfoMsgPack(base64.b64decode(assetbundle))
    print(f'new_assetbundle: {new_assetbundle}')
    global asset_bundle_folder_, data_server_folder_crc_
    asset_bundle_folder_ = new_assetbundle
    data_server_folder_crc_ = binascii.crc32(new_assetbundle.encode('utf8'))
    return 1


def UpdateAppVer(detail):
    matchObj = re.match('.*新ver.：(.*)、現.*', detail)
    if matchObj:
        global app_ver_
        app_ver_ = matchObj.group(1)
        print(f'new version: {app_ver_}')
    else:
        print('No matches')
        raise Exception('update app ver failed')


# ===== End =====

# ===== Telegram arguments =====
TelegramBotToken = ''
TelegramAdminId = ''


def SendMessageToAdmin(message):
    if TelegramBotToken and TelegramBotToken != 'nullvalue':
        nowtime = mytime.GetFormattedNowTime()
        response = requests.post(
            f'https://api.telegram.org/bot{TelegramBotToken}/sendMessage',
            data={'chat_id': TelegramAdminId, 'text': f'{nowtime}\n{message}'},
            timeout=20,
        )
        if not response.ok:
            print(f'Telegram notification failed: HTTP {response.status_code}')


# ===== End =====


# ===== Github api =====
def UploadFileToRepo(filename, content, commit='updated'):
    url = f'https://api.github.com/repos/{github_name_}/FGODailyBonusLog/contents/' + filename
    res = requests.get(url=url)
    jobject = json.loads(res.text)
    header = {
        'Content-Type': 'application/json',
        'User-Agent': f'{github_name_}_bot',
        'Authorization': 'token ' + github_token_,
    }
    content = str(base64.b64encode(content.encode('utf-8')), 'utf-8')
    form = {
        'message': commit,
        'committer': {
            'name': f'{github_name_}_bot',
            'email': 'none@none.none'
        },
        'content': content,
    }
    if 'sha' in jobject:
        form['sha'] = jobject['sha']
    form = json.dumps(form)
    result = requests.put(url, data=form, headers=header)
    print(result.status_code)


# ===== End =====

httpheader = {
    'Accept-Encoding': 'gzip, identity',
    'User-Agent': user_agent_,
    'Content-Type': 'application/x-www-form-urlencoded',
    'Connection': 'Keep-Alive, TE',
    'TE': 'identity',
}


def NewSession():
    return requests.Session()


def PostReq(s, url, data):
    res = s.post(url, data=data, headers=httpheader, verify=False).json()
    res_code = res['response'][0]['resCode']
    if res_code != '00':
        detail = res['response'][0]['fail']['detail']
        message = f'[ErrorCode: {res_code}]\n{detail}'
        SendMessageToAdmin(message)
        raise Exception(message)
    return res


def gameData():
    global app_ver_, data_ver_, date_ver_
    data = requests.get(
        f'{server_addr_}/gamedata/top?appVer={app_ver_}&dataVer={data_ver_}&dateVer={date_ver_}', verify=False
    ).json()

    if 'action' in data['response'][0]['fail'] and data['response'][0]['fail']['action'] == 'app_version_up':
        UpdateAppVer(data['response'][0]['fail']['detail'].replace('\r\n', ''))
        gameData()
        return

    if (
        data['response'][0]['success']['dateVer'] != date_ver_
        or data['response'][0]['success']['dataVer'] != data_ver_
    ):
        s = '*Need update*\n'
        s += f'appVer: {app_ver_}\n'
        s += f'dateVer: {date_ver_} Server: {data["response"][0]["success"]["dateVer"]}\n'
        s += f'dataVer: {data_ver_} Server: {data["response"][0]["success"]["dataVer"]}'
        SendMessageToAdmin(s)

        val = UpdateBundleFolder(data['response'][0]['success']['assetbundle'])
        if val == 1:
            data_ver_ = data['response'][0]['success']['dataVer']
            date_ver_ = data['response'][0]['success']['dateVer']
            new_data = {}
            new_data['global'] = {
                'appVer': app_ver_,
                'assetbundleFolder': asset_bundle_folder_,
                'dataServerFolderCrc': data_server_folder_crc_,
                'dataVer': data_ver_,
                'dateVer': date_ver_,
            }
            WriteConf(json.dumps(new_data))
        else:
            SendMessageToAdmin('Update failed')
