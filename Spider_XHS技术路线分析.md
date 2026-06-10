# Spider_XHS 技术路线分析

> 本文档是对 `referrence/Spider_XHS-master` 的逆向理解笔记,目的是为「从 0 实现自己的小红书运营系统」打底。
>
> 它分两层:
> - **第一层(架构层)**:这个项目是什么、怎么分层、各模块职责。
> - **第二层(集成层)**:它到底怎么运转、命脉在哪、脆在哪、你将来怎么用、为什么必须隔离。
>
> 配套阅读:`基于LangGraph的小红书两阶段多智能体运营系统架构方案.md`(你的系统设计)、`从0实现指导手册.md`(你的实施路线)。

---

## 0. 一句话定位

> **Spider_XHS 是一个能力很强、但会定期过期的「平台神经」黑盒。**
> 它逆向封装了小红书 PC 端 / 创作者 / 蒲公英 / 千帆四个平台的 HTTP 接口,把复杂的签名风控算法透明化了。你的系统是「大脑 + 流程编排」,通过一个很窄的接口面调用它。

它解决的核心问题:小红书没有开放接口,所有请求都要带一组用前端 JS 加密算出来的 header(`x-s` / `x-t` / `x-s-common` 等)。Spider_XHS 把浏览器里那段混淆 JS 抠出来,用 Node.js 在 Python 里跑一遍,从而能稳定读写平台数据。

---

## 1. 整体架构(分层)

```
spider/spider.py          ← 入口示例(采集笔记/用户/搜索)
        │
        ▼
apis/                     ← API 封装层(纯 HTTP 调用)
  xhs_pc_apis.py          PC端采集:笔记/用户/搜索/评论/消息(40 个方法)
  xhs_creator_apis.py     创作者平台:上传图集/视频、发布、作品列表
  xhs_pc_login_apis.py    PC端登录(二维码/手机验证码)
  xhs_creator_login_apis.py  创作者平台登录
  xhs_pugongying_apis.py  蒲公英 KOL 数据
  xhs_qianfan_apis.py     千帆分销商数据
        │
        ▼
xhs_utils/                ← 工具层
  xhs_util.py             PC端签名(调 JS 生成 x-s/x-t/x-s-common…)
  xhs_creator_util.py     创作者平台签名(另一套 JS + 发布 payload 组装)
  data_util.py            数据清洗 + Excel导出 + 媒体下载
  cookie_util.py          Cookie 字符串 → dict
  common_util.py          init() 读 .env、本地生成 a1/web_id、拉 sec 参数
  http_util.py            REQUEST_TIMEOUT = 15
        │
        ▼
static/*.js               ← 逆向出来的签名核心(execjs 调用)
  xhs_main_260411.js      PC端签名核心(最新版)
  xhs_creator_260411.js   创作者平台签名核心(最新版)
  xhs_rap.js              x-rap-param 本地 JSVMP 补环境生成
  xhs_creator_signature.js  上传媒体的 q-signature
  xhs_xray.js             x-xray-traceid
  ...
```

**依赖环境**:Python 3.10+(`PyExecJS requests loguru python-dotenv retry openpyxl aiohttp opencv-python numpy qrcode`)+ Node.js 20+(`crypto-js`、`jsdom`)。`PyExecJS` 是 Python 调 Node 的桥。

---

## 2. 核心心智模型:一次请求的完整生命周期

整个 Spider_XHS,无论采集还是发布,**所有**对小红书的请求都遵循同一套生命周期。吃透这个,剩下几十个 API 方法扫一眼就懂:

```
你的输入(url / 关键词 / 笔记内容)
   │
   ▼
① 解析 Cookie 字符串 → dict,取出 a1          (cookie_util.trans_cookies)
   │
   ▼
② 拼装请求 body / query 参数                  (各 api 方法内部)
   │
   ▼
③ 用 a1 + api路径 + body + method
   调 JS 算出签名 header                       (xhs_util / xhs_creator_util)
   x-s / x-t / x-s-common  ← 核心三件套
   (+ x-rap-param / x-b3-traceid / x-xray-traceid)
   │
   ▼
④ requests 发出去,带上 headers + cookies      (各 api 方法内部)
   │
   ▼
⑤ res_json["success"] / res_json["msg"] 判定成败
   │
   ▼
⑥ 返回统一三元组 (success, msg, data)
```

**关键洞察:`a1` 是一切的根。** 它是 Cookie 里的一个字段,签名算法的输入全靠它。Cookie 一失效,`a1` 变了或没了,第 ③ 步算出来的签名就是废的,小红书直接拒。这就是为什么「Cookie 时效性」是这类项目的死穴。

---

## 3. 签名链路详解(命脉,也是最脆的地方)

小红书的反爬核心,是要求每个请求带一组用前端 JS 加密算出来的 header。Spider_XHS 做的事,本质是把浏览器里那段混淆过的 JS 抠出来,用 Node.js(execjs)在 Python 里跑。

### 3.1 两套独立的签名(PC 与 Creator 分开)

**PC 端采集**(`xhs_util.py`):
```python
generate_request_params(cookies_str, api, data, method)
  └→ generate_headers()
       └→ generate_xs_xs_common(a1, api, data, method)
            └→ execjs 调 xhs_main_260411.js 的 get_request_headers_params()
               # 这一行是真正的黑魔法,JS 里是逆向出来的混淆代码
            返回 {xs, xt, xs_common}
```

**创作者平台发布**(`xhs_creator_util.py`):用的是**另一套 JS**(`xhs_creator_260411.js`),算法不同,因为 creator 站点和 PC 站点的风控是分开的。这也解释了为什么两个站点要各自一份 Cookie、各自一套签名工具。

### 3.2 各签名参数职责与脆弱性

| 参数 | 谁需要 | 怎么来 | 脆弱性 |
|---|---|---|---|
| `x-s` / `x-t` / `x-s-common` | 几乎所有接口 | JS 算 | **最核心**,改前端就失效 |
| `x-rap-param` | 只有高风控接口(`get_note_info`、`search_note`、`post_note`) | `xhs_rap.js` 本地 JSVMP 补环境 | 较新的风控层 |
| `x-b3-traceid` / `x-xray-traceid` | 链路追踪 | 随机生成,纯 Python | 不脆,随便造 |
| `search_id` | 搜索接口 | `(时间戳<<64)+随机` 转 base36 | 已用 Python 复刻,不依赖 JS |
| `a1` / `web_id` | 登录前 | crc32 + md5,纯 Python | 已复刻 |
| `q-signature` | 上传媒体到 COS | `xhs_creator_signature.js` 算 | 上传专用 |
| `sec_poison_id` / `websectiga` / `gid` | 部分风控 | 调 `as.xiaohongshu.com` + JSVMP | 较新 |

### 3.3 一个对架构极其重要的判断

- **能用 Python 本地算的**(traceid、search_id、a1、web_id):这个库已经复刻了,**不脆**。
- **必须调 JS 的**(x-s 系列、x-rap-param、q-signature):**就是定时炸弹**。

看更新日志的节奏:
```
25/07/15  更新 xs version56 & 创作者接口
26/04/11  签名算法升级至最新版,重构创作者 API
26/04/28  更新 PC 端搜索/笔记详情风控参数,新增 search_id 当前算法 + x-rap-param 本地生成
```
**几乎每隔 1~3 个月,小红书改一次前端,`static/*.js` 就得有人重新逆向替换。**

> **设计含义**:你绝对不要碰签名逻辑,也不要试图自己逆向。把 Spider_XHS 当成一个**会过期的黑盒依赖**,在它外面包一层防护,并接受「某天它突然全挂掉」是常态而非意外。

---

## 4. 你真正会调的集成面(就 6 个函数,别被几十个方法吓到)

`xhs_pc_apis.py` 有 40 个方法,但按两阶段方案,实际只会用到下面这几个。按里程碑标注:

### 4.1 阶段一 · M2 采集(只读)

```python
XHS_Apis().search_some_note(query, require_num, cookies_str, sort_type_choice=2)
# → (success, msg, note_list)   note_list 是搜索结果项的列表
# sort_type_choice: 0综合 / 1最新 / 2最多点赞 / 3最多评论 / 4最多收藏
# 做痛点分析建议用 2 或 4(抓高表现样本)

XHS_Apis().get_note_info(note_url, cookies_str)
# → (success, msg, res_json)    单篇笔记详情,带 x-rap-param 的高风控接口

XHS_Apis().get_note_all_comment(note_url, cookies_str)
# → (success, msg, comment_list)  评论 = 用户痛点的金矿

data_util.handle_note_info(note_info)   # 把嵌套 JSON 拍平成干净 dict
```

### 4.2 阶段一 · M4 发布(写入,高风险)

```python
XHS_Creator_Apis().post_note(noteInfo, cookies_str)
# noteInfo 是一个 dict,关键字段:
#   title / desc / media_type("image" | "video")
#   images: [图片字节, ...]   ← 注意是 bytes 不是路径!最多 15 张
#   video:  视频字节
#   topics: ["话题1", ...]
#   type:   0公开 / 1私密      ← 起步一定先用 1 私密测
#   postTime: 13位时间戳 / None(立即)

XHS_Creator_Apis().get_all_publish_note_info(cookies_str)
# → 已发布列表,复盘取数用
```

### 4.3 阶段二 · M6(满足条件才碰)

`QianFanAPI`(选品)、`PuGongYingAPI`(达人)—— 现阶段完全不用看。

> **结论**:你的整个系统跟 Spider_XHS 的接触面就这 6 个函数。这是好消息 —— 要隔离、要 mock、要加防护的面非常小。

---

## 5. 数据流转(以采集一篇笔记为例)

```
note_url
   │ get_note_info()         POST /api/sns/web/v1/feed,带 x-rap-param
   ▼
res_json['data']['items'][0]   ← 需要扒壳,数据藏在嵌套里
   │ handle_note_info()       把嵌套 JSON 扁平化成干净字段
   ▼
{note_id, title, desc, liked_count, image_list, video_addr, tags, ...}
   │ download_note()          按 "昵称_用户id/标题_笔记id/" 建目录
   ▼                          存 info.json + detail.txt + 图片/视频
   │ save_to_xlsx()           汇总导出 Excel
   ▼
落盘
```

**无水印资源处理**(`handle_note_info` + `get_note_no_water_img`):
- 图片:把 CDN 域名改写成 `ci.xiaohongshu.com/...?imageView2/format/jpeg` 输出 JPEG。
- 视频:从 `note_card.video.media.stream.h264[0].master_url` 取地址。

**发布链路更复杂**(`post_note`):
- 图集:逐张 `upload_media`(先 `get_fileIds` 拿上传凭证 → 算 `q-signature` → PUT 到 `ros-upload`)→ `get_post_note_image_data` 组装 payload → 签名 → POST 发布。
- 视频:多一步用 OpenCV 抽首帧做封面 + 提取元数据 + **轮询转码状态**(最多 20 次 × 3 秒 = 最坏卡 60 秒)。

---

## 6. 会绊倒你的坑(从代码里挖出来的,文档不会说)

1. **`post_note` 的 images 要 bytes,不是路径。**(`xhs_creator_apis.py:471` 示例是 `open(...).read()`)传错类型直接报错。

2. **返回三元组里 `data` 的位置不统一。** 有的方法返回完整 `res_json`(要再 `['data']['items'][0]` 扒壳),有的直接返回处理好的 list。封装时要统一掉这个差异。

3. **`success=False` 时 `msg` 可能是异常对象也可能是字符串。**(`spider.py:29` 里 `msg = e` 直接塞了异常)封装时要统一成结构化错误。

4. **视频发布有转码轮询**(`xhs_creator_apis.py:239`),最坏卡 60 秒。节点要考虑超时。

5. **无水印图片靠 URL 改写**,小红书一改 CDN 就可能失效的脏逻辑。

6. **`init()` 只读一个 `COOKIES` 变量**(`common_util.py:25`),但你要采集 + 发布两份 Cookie。config 层必须自己拆成 `COOKIES_PC` / `COOKIES_CREATOR`,不能直接用它的 `init()`。

7. **超时硬编码 15 秒**(`http_util.py`),除 `download_note` 有 `@retry` 外没有重试。高风控接口偶发失败正常,封装层要自己加**有限退避重试**(注意红线「失败即停,不要重试轰炸」,所以是有限退避,不是无限重试)。

---

## 7. 工程质量评价

**做得好:**
- 分层清晰,API 层和工具层解耦,容易扩展。
- 统一的 `(success, msg, data)` 三元组返回,错误处理一致。
- 翻页逻辑统一用 `cursor + has_more` 模式,所有 `get_*_all_*` 方法复用。
- JS 编译做了缓存(`_JS_CACHE` / `LazyStaticJS`),避免重复编译开销。

**风险与局限:**
- **签名 JS 是逆向产物,极易失效**(见 §3.3)。这是这类项目的根本脆弱性。
- **强依赖有效登录 Cookie**,有时效,失效要手动重抓。
- **封号风险**:README 自己也建议配代理。高频采集容易触发风控。
- **部署链路重**:依赖 Node.js + execjs 桥接,不是纯 Python。

---

## 8. 对「从 0 实现」的指导意义(承上启下)

把上面消化完,Spider_XHS 的定位应该非常清晰了:

> 它是「平台神经」黑盒,你的系统是「大脑 + 流程」,接触面只有 6 个函数。

这直接印证了实施手册 §5.2 的**薄封装隔离**设计。现在能更深刻理解为什么:

- **不是为了代码好看,而是因为 Spider_XHS 一定会塌。** 塌的时候你只想改 `platforms/` 一个目录,而不是满项目找哪里调了它。
- **`platforms/collector.py` 和 `creator.py` 这层要做的四件事**(正好对冲 §6 的坑 + 安全红线):
  1. **统一数据壳** —— 把三元组里 `data` 位置不一的问题(坑 2)在这层抹平。
  2. **统一错误结构** —— 把 `msg` 时而异常时而字符串(坑 3)收敛成结构化错误。
  3. **加延时 / 有限重试** —— 对冲坑 7 + 红线「低频拟人」「失败即停」。
  4. **发布前查人工确认标记** —— 落地红线「人工确认硬节点」。

### 8.1 隔离层接口设计建议(你自己实现时照这个签名写)

```python
# platforms/collector.py —— 包 XHS_Apis,对外只暴露业务语义
class Collector:
    def search_notes(self, topic: str, num: int, sort: str = "most_liked")
        -> Result[list[Note]]            # 已扒壳、已去标识化、已加延时
    def get_note_detail(self, note_url: str) -> Result[Note]
    def get_comments(self, note_url: str) -> Result[list[Comment]]
        # Comment 已去标识化:不含昵称/头像/主页/用户ID,只留 content + 互动数

# platforms/creator.py —— 包 XHS_Creator_Apis
class Creator:
    def publish(self, draft: Draft, *, human_approved: bool) -> Result[PostId]
        # human_approved=False 直接抛错,代码层拦死「无确认不发布」
    def list_published(self) -> Result[list[PublishedNote]]

# Result = 统一的结构化返回,替代 (success, msg, data) 三元组
# Note / Comment / Draft = 你自己的领域模型,不暴露小红书原始 JSON
```

**核心原则**:LangGraph 节点**永远不直接 import Spider_XHS**,只调你的 `Collector` / `Creator`。Spider_XHS 升级、换库、加防护,只动 `platforms/`,节点零改动。

---

## 9. 一页纸速记

```
请求生命周期:  Cookie取a1 → 拼参数 → 调JS签名 → requests发出 → 判success → 返回三元组
命脉:          a1 + 两套签名JS(PC / Creator),会随小红书改前端定期失效
你的接触面:    采集 search_some_note / get_note_info / get_note_all_comment
               发布 post_note / get_all_publish_note_info  (共6个)
必做的隔离:    platforms/ 薄封装 → 统一数据壳 + 统一错误 + 延时重试 + 人工确认拦截
心态:          把它当会过期的黑盒,接受它会塌,塌了只改 platforms/
```
