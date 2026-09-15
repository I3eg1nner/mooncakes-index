///|
/// M 规则（元数据）：moon.mod 层面的 typosquat / 官方仿冒 / 空壳 / 仓库不一致 / 依赖混淆

///|
/// 官方 moonbitlang 仓库名集合，不得被第三方仿冒
pub fn official_repo_names() -> Array[String] {
  ["core", "async", "x", "parser", "yacc", "quickcheck"]
}

///|
/// "author/repo" 的 repo 段；无斜杠时整个字符串即 repo
fn repo_of(name : String) -> String {
  match name.find("/") {
    Some(i) => name[i + 1:].to_owned()
    None => name
  }
}

///|
/// "author/repo" 的 author 段；无斜杠时为空
fn author_of(name : String) -> String {
  match name.find("/") {
    Some(i) => name[:i].to_owned()
    None => ""
  }
}

///|
/// URL 路径段（去掉 scheme 后按 "/" 切分）
fn url_segments(url : String) -> Array[String] {
  let t = url.trim(chars="/").to_owned()
  match t.find("://") {
    Some(p) => {
      let rest = t[p + 3:].to_owned()
      let segs : Array[String] = []
      for seg in rest.split("/") {
        segs.push(seg.to_owned())
      }
      segs
    }
    None => []
  }
}

///|
/// URL 的 repo 段（倒数第一段）；pub 供后续规则复用
pub fn repo_of_url(url : String) -> String {
  let segs = url_segments(url)
  if segs.length() >= 2 {
    segs[segs.length() - 1]
  } else {
    ""
  }
}

///|
/// URL 的 owner 段（倒数第二段）
fn owner_of_url(url : String) -> String {
  let segs = url_segments(url)
  if segs.length() >= 2 {
    segs[segs.length() - 2]
  } else {
    ""
  }
}

///|
/// M01：repo 名与 hotlist 中 repo 名 DL ≤2 且不同名 → High（每个模块至多一条，首个命中即止）
pub fn m01(m : Manifest, hotlist : Array[String]) -> Array[@engine.Finding] {
  let rd : @engine.RuleDef = {
    id: "M01",
    severity: @engine.High,
    category: @engine.Metadata,
    description: "typosquatting",
  }
  let repo = repo_of(m.name)
  let fs : Array[@engine.Finding] = []
  for hot in hotlist {
    let hrepo = repo_of(hot)
    if hrepo == repo {
      continue
    }
    // 短 repo 名（<5 字符）的 DL ≤2 碰撞过于随机（elk/pkl、json/jsoo）→ 不比对
    if repo.length() >= 5 && hrepo.length() >= 5 {
      if @matchers.damerau_levenshtein(repo, hrepo) <= 2 {
        fs.push(
          rd.finding(
            file="moon.mod",
            line=1,
            snippet=m.name,
            message="name similar to popular module \{hot}",
          ),
        )
        break
      }
    }
  }
  fs
}

///|
/// M02：author ≠ moonbitlang 但 repo ∈ 官方名集或 name 以 "moonbitlang/" 开头 → Critical
pub fn m02(m : Manifest) -> Array[@engine.Finding] {
  let author = author_of(m.name)
  let repo = repo_of(m.name)
  if author == "moonbitlang" {
    return []
  }
  if m.name.has_prefix("moonbitlang/") ||
    official_repo_names().iter().any(o => o == repo) {
    let rd : @engine.RuleDef = {
      id: "M02",
      severity: @engine.Critical,
      category: @engine.Metadata,
      description: "official impersonation",
    }
    [
      rd.finding(
        file="moon.mod",
        line=1,
        snippet=m.name,
        message="impersonates official moonbitlang module",
      ),
    ]
  } else {
    []
  }
}

///|
/// M03：readme 过短且无测试且 name 非空 → Medium（空壳模块）
pub fn m03(
  m : Manifest,
  readme_len : Int,
  has_tests : Bool,
) -> Array[@engine.Finding] {
  if readme_len < 200 && !has_tests && m.name.length() > 0 {
    let rd : @engine.RuleDef = {
      id: "M03",
      severity: @engine.Medium,
      category: @engine.Metadata,
      description: "empty shell",
    }
    [
      rd.finding(
        file="moon.mod",
        line=1,
        snippet=m.name,
        message="no substantial readme and no tests",
      ),
    ]
  } else {
    []
  }
}

///|
/// M04：repository 为空 → Low；URL owner 段与模块 author 不一致 → Medium
pub fn m04(m : Manifest) -> Array[@engine.Finding] {
  if m.repository.length() == 0 {
    let rd : @engine.RuleDef = {
      id: "M04",
      severity: @engine.Low,
      category: @engine.Metadata,
      description: "missing repository",
    }
    return [
      rd.finding(
        file="moon.mod",
        line=1,
        snippet="",
        message="no repository field",
      ),
    ]
  }
  let owner = owner_of_url(m.repository)
  let author = author_of(m.name)
  // GitHub 登录名大小写不敏感（Across2005/across2005 为同一 owner）
  if owner.length() > 0 &&
    author.length() > 0 &&
    owner.to_lower() != author.to_lower() {
    let rd : @engine.RuleDef = {
      id: "M04",
      severity: @engine.Medium,
      category: @engine.Metadata,
      description: "repository owner mismatch",
    }
    [
      rd.finding(
        file="moon.mod",
        line=1,
        snippet=m.repository,
        message="repository owner \{owner} != module author \{author}",
      ),
    ]
  } else {
    []
  }
}

///|
/// M05：依赖 repo 名与 hotlist/官方名 DL ≤2（排除同名）→ High（每依赖一条）
pub fn m05(m : Manifest, hotlist : Array[String]) -> Array[@engine.Finding] {
  let rd : @engine.RuleDef = {
    id: "M05",
    severity: @engine.High,
    category: @engine.Metadata,
    description: "dependency confusion",
  }
  let fs : Array[@engine.Finding] = []
  for dep in m.deps {
    let drepo = repo_of(dep)
    // 与 M01 相同的短名护栏：双方 repo 名均 ≥5 才比对（x/y、x/ts 类碰撞过于随机）
    let near_hot = hotlist
      .iter()
      .any(h => {
        let hrepo = repo_of(h)
        hrepo != drepo &&
        drepo.length() >= 5 &&
        hrepo.length() >= 5 &&
        @matchers.damerau_levenshtein(drepo, hrepo) <= 2
      })
    let near_official = official_repo_names()
      .iter()
      .any(o => {
        o != drepo &&
        drepo.length() >= 5 &&
        o.length() >= 5 &&
        @matchers.damerau_levenshtein(drepo, o) <= 2
      })
    if near_hot || near_official {
      fs.push(
        rd.finding(
          file="moon.mod",
          line=1,
          snippet=dep,
          message="dependency name close to known module",
        ),
      )
    }
  }
  fs
}
