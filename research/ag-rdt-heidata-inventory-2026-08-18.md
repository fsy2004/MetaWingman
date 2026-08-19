# ag-rdt-living-update 家族：2022 更新版论文与 heiDATA 记录在线核实清单

- 核实日期：2026-08-18（UTC，一次性在线核实，全部内容来自实际抓取的网页/API 响应）
- 对应计划文件：`research/benchmark-material-plans/ag-rdt-living-update.json`（review_family_id = covid19-antigen-dta-living）
- 核实方式：read_page 抓取（Zenodo 页面 + Zenodo API + heiDATA Dataverse API + PLoS 文章页 + web_search 交叉检索）；**未下载任何数据文件本体**，未修改仓库其他文件，未做 git 提交。
- 只读声明：以下所有数值、日期、license 均为本次会话实际看到的内容；未能获取的内容一律标注 `not verified`。

---

## 1. 论文信息（2021 原版 + 2022 更新版）

### 1.1 2021 原版（living systematic review 首发）
- 标题：*Accuracy of novel antigen rapid diagnostics for SARS-CoV-2: A living systematic review and meta-analysis*
- 期刊：PLOS Medicine 18(8): e1003735
- DOI：https://doi.org/10.1371/journal.pmed.1003735
- 发表日期：2021-08-12（Received 2021-02-26; Accepted 2021-07-14）
- PMID：34383750（经 web_search 检索快照核对，未直接打开 PubMed 页面——cookie 墙）
- 检索截止日期：**2021-04-30**（原文 Methods："We performed the search up until 30 April 2021."，与计划文件 `update_cutoff = 2021-04-30` 一致）
- 纳入规模：133 项研究、214 个临床准确性数据集、112,323 份样本（来自 PLOS 摘要）
- Data Availability 声明：**指向 Zenodo**——"All raw data is publicly available under https://zenodo.org/record/4924035"
- 来源 URL：https://journals.plos.org/plosmedicine/article?id=10.1371/journal.pmed.1003735

### 1.2 2022 更新版（本次核实的主要对象）
- 标题：*Accuracy of rapid point-of-care antigen-based diagnostics for SARS-CoV-2: An updated systematic review and meta-analysis with meta-regression analyzing influencing factors*
- 期刊：PLOS Medicine 19(5): e1004011
- DOI：https://doi.org/10.1371/journal.pmed.1004011
- 发表日期：2022-05-26（Received 2022-02-09; Accepted 2022-05-04）
- PMID：35617375（经 web_search 检索快照核对）
- 检索截止日期：**2021-08-31**（原文 Methods："We performed the search biweekly through August 31, 2021."，与计划文件 `update_cutoff = 2021-08-31` 一致）
- 纳入规模：194 项研究、221,878 次 Ag-RDT（来自 PLOS 摘要）
- Data Availability 声明：**指向 heiDATA**——"All data are available from https://doi.org/10.11588/data/T3MIB0."
- 来源 URL：https://journals.plos.org/plosmedicine/article?id=10.1371/journal.pmed.1004011

### 1.3 living review 时间结构（2022 论文 Introduction 原文，用于阻塞项③的边界证据）
- 2020-10 起开展 living SR（网站 www.diagnosticsglobalhealth.org，每周更新至 2021-08-31）
- 2021-02 首发（覆盖文献截至 **2020-12-15**）
- 同行评审后纳入再 4 个月文献（截至 **2021-04-30**）出版更新版（即 1.1，2021-08-12）
- 2022-05-26 出版本次更新（即 1.2，文献截至 2021-08-31）
- 来源 URL：同上 1.2。

---

## 2. heiDATA 记录：DOI 10.11588/DATA/T3MIB0

### 2.1 记录基本信息（来源：Dataverse API，`GET https://heidata.uni-heidelberg.de/api/datasets/:persistentId/versions/:latest?persistentId=doi:10.11588/DATA/T3MIB0`）
- 标题：*Accuracy of rapid point-of-care antigen-based diagnostics for SARS-CoV-2: an updated systematic review and meta-analysis with meta regression analyzing influencing factors [Research Data]*
- 记录 DOI：https://doi.org/10.11588/DATA/T3MIB0
- 记录页面：https://heidata.uni-heidelberg.de/dataset.xhtml?persistentId=doi:10.11588/data/T3MIB0
- 仓库：heiDATA（Heidelberg 大学研究数据仓库，Dataverse 软件）；所属 dataverse：`idtm`（Division of Infectious Disease and Tropical Medicine）
- 当前版本：**V1.1**（versionNumber 1, minor 1；内部版本 id 766），状态 RELEASED
- 发布日期：2022-02-25（releaseTime 2022-02-25T12:14:25Z）
- 数据集联系人：Claudia M. Denkinger（Claudia.Denkinger@uni-heidelberg.de）
- 记录内 publication 元数据：指向 medRxiv 预印本 https://doi.org/10.1101/2022.02.11.22270831（记录发布于 2022-02-25，早于 PLOS 正式发表 2022-05-26，故元数据未更新为正式论文 DOI；正式论文 Data Availability 反向指向本记录，见 1.2）

### 2.2 License（实际看到的值）
- **CC BY-NC-ND 4.0**（Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International）
- API 原文（termsOfUse 字段，V1.0 与 V1.1 一致）：
  `Licensed under Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International (CC BY-NC-ND 4.0).`
- 含义：允许非商业使用与分享原样副本；**禁止商业使用、禁止制作衍生作品**。
- 对比：2021 Zenodo 工件为 **CC BY 4.0**（见第 3 节）——两个版本 license 不同，后者更宽松。

### 2.3 文件清单（来源：Dataverse API，获取方式 = API）
最新版本 V1.1 文件（唯一文件）：

| 文件名 | 大小（字节） | 格式（contentType） | 仓库 MD5 | 文件级 DOI | restricted | 创建/发布 |
|---|---|---|---|---|---|---|
| Accuracy_of_rapid_point-of-care_antigen-based_diagnostics_for_SARS-CoV-2.xlsx | 674,749 | xlsx（application/vnd.openxmlformats-officedocument.spreadsheetml.sheet） | 8541981cc4ec230b2a8c67e885fac4a6 | doi:10.11588/DATA/T3MIB0/FIDTR9（https://doi.org/10.11588/DATA/T3MIB0/FIDTR9） | false（公开可下载） | 2022-02-09 创建 / 2022-02-25 发布 |

- 数据集整体文件数：1（搜索 API `total_count` 与 `fileCount: 1` 一致）。
- 补充：同一记录存在两个已发布版本，文件**内容字节级相同**（关键不可变性证据）：
  - V1.0（id 753，release 2022-02-25T09:44:49Z）：文件名 `Covid Ag SR_MA Update.xlsx`，大小 674,749，MD5 `8541981cc4ec230b2a8c67e885fac4a6`，storageIdentifier `file://17ede1ef542-b226962907d6`，dataFile id 6400，文件 DOI 同为 FIDTR9
  - V1.1（id 766，release 2022-02-25T12:14:25Z）：文件名改为描述性长名，其余（大小/MD5/storageIdentifier/dataFile id/文件 DOI）**全部相同**
  - 即：V1.0 → V1.1 仅重命名文件，底层 blob 未变（相同 MD5 + 相同 storageIdentifier）。版本家族无 V2。

---

## 3. 补充核实：Zenodo record 4924035（2021 密封工件）与 heiDATA 的关系

- 来源：Zenodo 页面 https://zenodo.org/records/4924035（read_page）＋ Zenodo API `https://zenodo.org/api/records/4924035`
- 记录：*The accuracy of novel antigen rapid diagnostics for SARS-CoV-2: a living systematic review and meta-analysis.*（2021-06-12 发布，Version 2，revision 7）
- DOI：10.1101/2021.02.26.21252546（记录本身使用 medRxiv 预印本 DOI 作记录 DOI）
- License：**CC BY 4.0**（API `license.id = "cc-by-4.0"`，access_right = open）
- 文件：`Covid Ag SR_MA Update V2.xlsx`，531,709 字节，md5 `0f2284693a4e1d7fe844e594539756e5`（与计划文件 531,709 字节一致；计划文件中的 expected_sha256 8c2dfe6f… 为本地计算值，Zenodo 侧仅提供 MD5）
- **Zenodo 记录是否链接 heiDATA：否。** API `related_identifiers` 仅有 1 条：`{"identifier":"10.1101/2021.02.26.21252546","relation":"isRequiredBy"}`——链接的是 medRxiv 预印本 DOI，无任何 heiDATA 记录链接。2021 论文的 Data Availability 也只指向 Zenodo（见 1.1）。
- 结论：heiDATA 记录（T3MIB0）是 **2022 更新版** 的独立数据工件，与 2021 Zenodo 工件为同一 living review 家族的两代数据，由 2022 论文 Data Availability 声明官方链接（1.2）。

---

## 4. 三个阻塞项逐条判定

| # | 阻塞项（计划文件原文） | 判定 | 证据 |
|---|---|---|---|
| ① | Inventory and hash the immutable 2022 heiDATA files. | **部分解决**（清单 + 不可变性已解决；本地 SHA-256 待补） | 清单：1 个文件，674,749 字节，xlsx，文件 DOI FIDTR9，公开可下载（Dataverse API，2.3 节）。不可变性：V1.0/V1.1 文件内容同一（相同 MD5 8541981cc4…、相同 storageIdentifier、相同文件 DOI，仅重命名），版本家族无 V2。哈希：仓库方 MD5 `8541981cc4ec230b2a8c67e885fac4a6` 已记录（API 字段 `checksum.type=MD5`）；**本地 SHA-256 未计算（not verified）**——本任务约束不下载数据本体，需在正式拉取该文件时计算并核对。 |
| ② | Verify the later repository license. | **已解决**（结论与预期相反：非 CC BY，而是 CC BY-NC-ND 4.0） | V1.0 与 V1.1 两个版本的 `termsOfUse` 字段均为 **CC BY-NC-ND 4.0**（Dataverse API，2.2 节）。⚠️ 影响：2022 heiDATA 工件比 2021 Zenodo 工件（CC BY 4.0）更严格——禁止商业使用、禁止衍生作品。若将其纳入材料包，只能作"引用-只读"对照，不可再分发/再加工；计划文件 `license_assessment` 中 `pack_redistributable: true` 仅对 2021 CC BY 工件成立，需对 2022 工件单独标注 `not redistributable`。 |
| ③ | Construct a pre-update operational corpus that excludes later evidence. | **部分解决**（时间边界证据已在线核实；语料本体构建属本地操作） | 边界证据（均已核实，见 1.1–1.3）：2021 版检索截至 2021-04-30；2022 更新版检索截至 2021-08-31；living review 每周更新至 2021-08-31；2022 heiDATA 工作簿（194 项研究）本身即"后更新证据"，应从 pre-update 语料排除。语料"构建"（检索去重、筛选、与密封 2021 工作簿对齐等）依赖本地材料（Zenodo 密封工作簿 + run lock），超出本次只读在线核实范围，需本地执行。 |

---

## 5. not verified 清单（明确未获取/未核实内容）

1. **2022 heiDATA 文件（T3MIB0/FIDTR9）的本地 SHA-256**：未计算（未下载本体，仅记录仓库方 MD5）。
2. **2022 heiDATA 工作簿的内容/工作表结构**：未下载、未打开，无法核实其内容与 2021 工作簿的差异。
3. **PMID 34383750 / 35617375 的 PubMed 页面原文**：PubMed 有 cookie 墙，PMID 及期刊卷期页信息来自 web_search 结果快照与 PLOS 文章页（PLOS 页为主要来源，PMID 为检索快照）。
4. 计划文件中 `historical_boundaries` 的 `update_cutoff = 2021-04-30` 的"首发版本"性质：已由 2021 论文（检索至 2021-04-30）与 2022 论文引言（"published an updated review … until April 30, 2021"）交叉印证；2021-02 首发版本的截止 2020-12-15 来自 2022 论文引言（未直接核对 2021 年 medRxiv v1 页面）。
5. Zenodo 记录 4924035 除主文件外无其他文件（API files 数组仅 1 项，已核实，非未核实项）。

---

## 6. 来源清单（本次实际读取的 URL）

- https://zenodo.org/records/4924035 （页面）
- https://zenodo.org/api/records/4924035 （API：license、related_identifiers、文件 md5/大小）
- https://journals.plos.org/plosmedicine/article?id=10.1371/journal.pmed.1003735 （2021 论文：检索截止、Data Availability）
- https://journals.plos.org/plosmedicine/article?id=10.1371/journal.pmed.1004011 （2022 论文：检索截止、Data Availability、living review 时间结构）
- https://heidata.uni-heidelberg.de/api/datasets/:persistentId/versions/:latest?persistentId=doi:10.11588/DATA/T3MIB0 （API：license、文件清单、MD5）
- https://heidata.uni-heidelberg.de/api/datasets/:persistentId/versions?persistentId=doi:10.11588/DATA/T3MIB0 （API：版本历史 V1.0/V1.1）
- https://heidata.uni-heidelberg.de/api/datasets/:persistentId/versions/1.0?persistentId=doi:10.11588/DATA/T3MIB0 （API：V1.0 文件清单/原名/MD5）
- https://heidata.uni-heidelberg.de/api/search?q=antigen%20rapid （API：检索定位 T3MIB0 与相关记录 P9JEPG、FSPQL4 等）
- https://doi.org/10.11588/DATA/T3MIB0 ；https://doi.org/10.11588/DATA/T3MIB0/FIDTR9 （记录/文件 DOI）
- 交叉检索：web_search "Brümmer living systematic review 2022 update"、"10.1371/journal.pmed.1004011"、"heidata rapid point-of-care antigen"（Firecrawl 检索，用于定位与 PMID 核对）
