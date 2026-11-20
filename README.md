# FGODailyBonus
`Fate/Go`每日签到脚本，自`2020/06/23`以来稳定运行中。  
**但不排除有被封号的可能性，使用后果请自负。**

fork 自 [hexstr/FGODailyBonus](https://github.com/hexstr/FGODailyBonus)，在原版基础上做了这些修复与增强：

- 修复 `private_key.pem` 无法被新版 OpenSSL 解析（`ASN.1 parsing error`）
- 支持**私有日志仓库**（改用 GitHub API 读写，不再依赖公开的 raw 地址）
- 添加自动种苹果功能
- 添加 Docker 定时触发(Actions触发延迟可以考虑使用)

> [!NOTE]
> 现在FGO新增了`play integrity api`，使用这个脚本可能造成账号被标记，导致登录时需要满足`App Check`的条件，不然会出现`99-`开头的错误代码
> 
> ![a0](imgs/a0.jpg)
> 
> 经过测试，只需要设备通过`MEETS_BASIC_INTEGRITY`即可正常登录
> 
> ![a1](imgs/a1.jpg)
> 
> ![a2](imgs/a2.jpg)
>
> ![a4](imgs/a4.jpg)
> 
> 否则依然会出错
> 
> ![a3](imgs/a3.jpg)

## 使用
0. 首先提取`账号`、`密码`和`id`，文件位于`/sdcard/Android/data/com.aniplex.fategrandorder/files/data/54cc790bf952ea710ed7e8be08049531`，用记事本打开，从`字母Z`复制到结尾
   ![0](imgs/0.jpg)
   
   然后搜索`C# Online Compiler`，比如[这个网站](https://www.onlinegdb.com/online_csharp_compiler)，把`CertificateExtractor.cs`中的内容复制粘贴到编辑框，修改第九行`YourCertificate`为你从`54cc790bf952ea710ed7e8be08049531`复制的内容，点击`Run`
   ![0-1](imgs/0-1.jpg)

   输出的结果对应`GAME_AUTHKEYS`、`GAME_SECRETKEYS`和`GAME_USERIDS`所需要的值

1. 创建一个名为`FGODailyBonusLog`的仓库，确保`branch`为`main`，点击`creating a new file`
    ![1](imgs/1.jpg)

2. 新建`cfg.json`并复制粘贴
   ```json
   {"global": {"appVer": "2.54.0", "assetbundleFolder": "trb3ulHJR4lI/", "dataServerFolderCrc": 610168911, "dataVer": 1419, "dateVer": 1655046000}}
   ```
   然后点击`Commit new file`
    ![2](imgs/2.jpg)

3. 创建用于读写 `FGODailyBonusLog` 的 GitHub Token，存为主仓库的 Actions Secret `VERY_IMPORTANT_TOKEN`。推荐 fine-grained token：只选 `FGODailyBonusLog`，授予 `Contents: Read and write`。classic token 需 `repo` scope，授权范围更大；不要把 Token 写进仓库。
    ![3](imgs/3.jpg)

    下图是旧版 classic token 页面的示例，以 GitHub 当前界面为准。  
    ![3-1](imgs/3-1.jpg)

4. `fork`[这个repo](https://github.com/hexstr/FGODailyBonus)，点击`Settings`->`New repository secret`来创建`secrets`。脚本需要的`secrets`参考[secrets列表](#secrets列表)。
   ![4](imgs/4.jpg)

5. 点击`Actions`并启用
   ![5](imgs/5.jpg)

6. 用 [容器触发版 workflow](fgo-dispatch/run.yml) 替换 `.github/workflows/run.yml`：它只允许 `workflow_dispatch`，不使用 GitHub 的 `schedule` 或 `push`，提交代码不会触发签到。部署前可在 Actions 页点击 `Run workflow` 手动测试。

7. 点击`Actions`查看手动运行结果
   ![7](imgs/7.jpg)

   还有`telegram 通知`  
   ![7-1](imgs/7-1.jpg)

   和`日志文件`  
   ![7-2](imgs/7-2.jpg)

8. 需要每日自动运行时，按下方 [Docker 定时触发](#docker-定时触发) 部署容器。不要同时保留 `schedule`，否则可能同一天签到两次。

> [!WARNING]
> 上面的 `cfg.json` 是上游示例，版本信息可能过期。不要在公开仓库上传游戏凭据、Token 或签到日志。私有日志仓库需要带 Token 的 GitHub Contents API 读取配置；上游原版仅通过公开 raw URL 读取，不能直接读取私有仓库。

## Docker 定时触发

VPS 上的容器仅负责调用 GitHub 的 `workflow_dispatch` API；游戏签到仍由 GitHub Actions 执行。容器每天按上海时间在 **07:00–08:00** 随机选定一分钟触发。如果 VPS 停机错过该时间段，当天跳过，不会补跑；重启后保留当天已选时间与发送状态。

### 准备

1. 确认 `.github/workflows/run.yml` 包含 `workflow_dispatch:`，且不包含 `schedule:` 和 `push:`。仓库的 Actions Secrets 仍按上文配置。
2. 另建一个**只授权 `FGODailyBonus`** 的 fine-grained Token，权限为 `Actions: Read and write`。它不同于用于读写 `FGODailyBonusLog` 的 Token。
3. 在 VPS 安装 Docker，将 [Dockerfile](fgo-dispatch/Dockerfile) 和 [scheduler.py](fgo-dispatch/scheduler.py) 放在同一目录。新建 `fgo-token.txt`，里面只写一行触发 Token；执行 `chmod 600 fgo-token.txt`。不要提交这个文件。

> [!IMPORTANT]
> 本教程中的文件链接要求将 `fgo-dispatch/` 目录（至少包含 `Dockerfile`、`scheduler.py` ）一并上传到 fork；VPS 上只需前两个文件。不要提交真实 Token 或 `.env`。

### 构建与运行

在 VPS 进入放有 Dockerfile 的目录后执行：

```bash
docker build -t fgo-dispatch .
docker volume create fgo-dispatch-state
read -r GH_TOKEN < fgo-token.txt
docker run -d \
  --name fgo-dispatch \
  --restart unless-stopped \
  -e GH_TOKEN="$GH_TOKEN" \
  -e GH_REPO=zero3334/FGODailyBonus \
  -e GH_WORKFLOW=run.yml \
  -e GH_REF=master \
  -v fgo-dispatch-state:/data \
  fgo-dispatch
unset GH_TOKEN
docker logs fgo-dispatch
```

日志先显示当天抽到的时间。到点出现 `GitHub accepted dispatch (204)` 表示 GitHub 接受请求，**不代表签到成功**；仍须到仓库 Actions 页面查看 `Test` 步骤。若返回 HTTP 401/403，请检查 Token 权限；HTTP 404 请核对仓库名、工作流文件名与默认分支。

### 手动验证

下面的命令会**真实签到并尝试存 AP**，不会取消容器当天的计划，可能导致同一天重复执行。确认后在 VPS 上运行：

```bash
read -r GH_TOKEN < fgo-token.txt
curl -sS -o /dev/null -w '%{http_code}\n' \
  -X POST \
  -H "Authorization: Bearer $GH_TOKEN" \
  -H 'Accept: application/vnd.github+json' \
  -H 'X-GitHub-Api-Version: 2022-11-28' \
  https://api.github.com/repos/zero3334/FGODailyBonus/actions/workflows/run.yml/dispatches \
  -d '{"ref":"master"}'
unset GH_TOKEN
```

返回 `204` 后，到 Actions 页面确认新的 `workflow_dispatch` 是否成功。手动调用不会出现在容器日志里。

> [!CAUTION]
> Docker 环境变量中的 Token 可被有 Docker 管理权限的人通过 `docker inspect` 查看。不要在不可信的共享 VPS 上运行，泄露后立即撤销 Token。

> 如需恢复 GitHub 自带的定时签到，在 .github/workflows/run.yml 中将开头的触发配置改为：

on:
  workflow_dispatch:
  schedule:
    - cron: '30 23 * * *'

这里的 30 23 * * * 是 UTC 每天 23:30，对应北京时间次日 07:30。GitHub 定时任务可能延迟，不保证准点运行。恢复前先用 docker stop fgo-dispatch 停止 VPS 上的容器，避免同一天执行两次。

## secrets列表
| key                  | value                                                                 | description                                 |
|----------------------|-----------------------------------------------------------------------|---------------------------------------------|
| GAME_AUTHKEYS        | RaNdOmStRiNg1234:randomAAAAA=,RaNdOmStRiNg1235:randomAAAAA=           | 需要签到的账号，多个账号使用英文逗号","分隔 |
| GAME_SECRETKEYS      | RaNdOmStRiNg1234:randomAAAAA=,RaNdOmStRiNg1235:randomAAAAA=           | 对应的密码，多个账号使用英文逗号","分隔     |
| GAME_USERAGENT       | Dalvik/2.1.0 (Linux; U; Android 11; Pixel 5 Build/RD1A.201105.003.A1) | 伪装UA，填入nullvalue使用默认值             |
| GAME_USERIDS         | 60951234,60951235                                                     | 账号id                                      |
| GAME_VERCODE         | 48a1e86bdbb80b4795204d447cfc073ce21b132a5bd5b096cb919830b1d3b93e      | ←填这个就行                                 |
| TELEGRAM_ADMIN_ID    | nullvalue                                                             | 接收通知的telegram id，不需要就填nullvalue  |
| TELEGRAM_BOT_TOKEN   | nullvalue                                                             | 发送通知的bot token，不需要就填nullvalue    |
| VERY_IMPORTANT_NAME  | your_github_name                                                      | 填你的github name                           |
| VERY_IMPORTANT_TOKEN | ghp_uCwPxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx                              | 第三步申请的access token                    |

## 致谢与许可

- 原始项目：[hexstr/FGODailyBonus](https://github.com/hexstr/FGODailyBonus)
- 许可：[MIT](LICENSE)
