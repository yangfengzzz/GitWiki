# GitWiki

GitWiki 是一个运行在本机的 GitHub 项目资料库。它把 Star、自己拥有的仓库、元数据和 README 缓存在 SQLite 中，提供分类浏览、全文搜索、标签、笔记和一键同步。页面延续最初确认的三栏出版式设计。

## 启动

需要 Python 3.11+、[GitHub CLI](https://cli.github.com/) 和能运行 Codex SDK 的 Codex 登录。当前电脑已经通过 `gh` 登录，仓库中的 `.venv` 也已安装依赖。

```sh
cd /Users/yangfeng/Desktop/GitWiki
.venv/bin/python server.py
```

打开 <http://127.0.0.1:4173/>。服务仅监听本机地址。若在另一台电脑启动：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
gh auth login
.venv/bin/python server.py
```

GitHub 令牌从 `gh auth token` 读取，仅保存在服务进程内存中；也可以用 `GITHUB_TOKEN` 环境变量提供。GitWiki 只向 GitHub 发送读取请求，不会替你 Star 或修改 GitHub Lists。

## 已实现

- 读取全部 Star 及收藏时间，保存仓库名称、简介、语言、topics、Star 数、最近更新时间等信息。
- 读取登录账号本人拥有的公开及有权限访问的私有仓库；「我的项目」单独浏览和同步。与 Star 重叠的仓库按全名合并为一条记录，保留原分类、标签和笔记。
- 读取 README 并后台缓存；点开一个项目时，也会立即读取它的 README。可搜索已经缓存的 README 内容。
- 使用 25 个主题组、143 个细分类组成的本地分类树，涵盖机器人、视觉、几何、科学计算、游戏、媒体、量化金融、Web 与软件工具。旧的 32 个 GitHub List 只保存在参考表中，不直接决定新分类。
- 初次导入先根据仓库元数据做关键词归类，再由 Codex SDK 结合仓库名、简介、topics 和 README 摘要处理信息不足的项目。没有缓存的 README 会在分类前读取；README 也缺失或无法可靠判断时，项目留在「未分类」。以后新同步的 Star 也先进入「未分类」，等待手动整理。
- 可运行一次全量 Codex 复核：逐一读取缓存的 README 介绍与章节，重新为每个 Star 选择 0–3 个合适的细分类。一个项目有多个明确的核心用途时可进入多个分类；信息不足时留在「未分类」。旧分类不作为判断依据。每批结果会记录进度，服务重启后继续；运行期间新增的手动分类会保留。
- 扩充目录后可单独复核未分类项目：Codex 只为仍未归类的 Star 选择贴切的类别，资料不足的项目继续留在「未分类」。复核按批记录结果，服务重启后从剩余项目继续，不覆盖运行期间的手动分类。
- 对我的项目按缓存 README 复核分类；已有分类保留，Codex 只补充明确相关的主要用途。每次同步只重新检查新增或有新提交的仓库，进度可在服务重启后继续。
- 支持一个项目属于多个分类、拖放归类、批量归类、新建/编辑/删除分类、个人标签和自动保存的笔记。含子分类的主题需先整理子分类才能删除。
- 按分类、最近收藏、我的项目、未分类浏览；按项目元数据、标签、笔记和已缓存 README 搜索；按收藏时间、更新时间、Star 数或名称排序。
- 一键重新同步 Star 和我的项目，也可单独同步我的项目。同步保留本地分类、标签和笔记；仓库有新提交时会重新缓存 README。GitHub 上取消 Star 且不再由本人拥有的项目会从当前资料库视图中移除。

## 数据与运行状态

数据库在 `data/gitwiki.sqlite3`，已被 `.gitignore` 排除。它含私有仓库的元数据和 README，以及你的个人分类和笔记，建议定期备份。分类定义在 `taxonomy.json`，归类关键词在 `taxonomy_keywords.json`。已导入的数据不会因为修改这些文件而自动重置。

同步、README 缓存和分类在后台进行。顶部状态会显示进度；关闭服务会中断当前批次，下次启动后可继续。初次分类只处理尚未归类的项目；主动启动的全量复核会重新判断全部 Star 的分类，同时保留标签和笔记。README 缓存使用少量并发请求，遇到 GitHub 限流会暂停，可稍后重新启动。

## 验证

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check live.js
```

GitHub API 访问通过 `gitwiki/github.py` 实现；Codex SDK 用于初次分类和全量复核。前端依赖的 Markdown-it 和 DOMPurify 已存放在 `vendor/`，无需运行 npm 服务。
