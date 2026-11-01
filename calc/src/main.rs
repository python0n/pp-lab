//! pp_lab: recalculates scores with a chosen pp formula.
//!
//! Input (stdin, JSON):
//!   {"variant": "osu_2025_10", "scores": [{"id": 1, "map": "/path/123.osu", "mode": 0,
//!     "mods": 72, "n300": 500, "n100": 3, "n50": 0, "ngeki": 0, "nkatu": 0,
//!     "nmiss": 0, "combo": 812, "score": 12345678}, ...]}
//! Output (stdout, JSON): a list in the same order:
//!   [{"id": 1, "pp": 312.5, "stars": 6.1, "aim": .., "speed": .., "acc": .., "fl": .., "reading": .., "error": null}]
//!
//! Calculator: instead of hit counts "acc" (e.g. 98.5) can be given and "combo" left out,
//! then a full combo is calculated; without "n300" the remaining objects count as 300s.
//! The output also has the map's "max_combo".
//!
//! `pp_lab --variants` prints the supported variants.

use std::collections::HashMap;
use std::io::{self, Read};

use rayon::prelude::*;
use serde::{Deserialize, Serialize};

const NIGHTCORE: u32 = 512;
const DOUBLETIME: u32 = 64;

/// (id, modes, technical description)
const VARIANTS: &[(&str, &[u8], &str)] = &[
    ("tsg", &[0, 1, 2, 3], "akatsuki-pp b96019f - bancho.py's default formula"),
    ("osu_2026_07", &[0, 1, 2, 3], "rosu-pp pp-update 072ed25 - osu! since July 2026"),
    ("osu_2025_10", &[0, 1, 2, 3], "rosu-pp 4.0 - osu! Oct 2025 - Jul 2026"),
    ("osu_2025_03", &[0], "rosu-pp-older osu_2025"),
    ("osu_2024", &[0], "rosu-pp-older osu_2024"),
    ("osu_2022", &[0], "rosu-pp-older osu_2022"),
    ("osu_2021_nov", &[0], "rosu-pp-older osu_2021_november"),
    ("osu_2021_jul", &[0], "rosu-pp-older osu_2021_july"),
    ("osu_2021_jan", &[0], "rosu-pp-older osu_2021_january"),
    ("osu_2019", &[0], "rosu-pp-older osu_2019"),
    ("osu_2018", &[0], "rosu-pp-older osu_2018"),
    ("osu_2015_apr", &[0], "rosu-pp-older osu_2015_april"),
    ("osu_2015_feb", &[0], "rosu-pp-older osu_2015_february"),
    ("osu_2014_jul", &[0], "rosu-pp-older osu_2014_july"),
    ("osu_2014_may", &[0], "rosu-pp-older osu_2014_may"),
];

#[derive(Deserialize)]
struct Input {
    variant: String,
    scores: Vec<ScoreInput>,
}

#[derive(Deserialize, Clone)]
struct ScoreInput {
    id: i64,
    map: String,
    #[serde(default)]
    mode: u8,
    #[serde(default)]
    mods: u32,
    #[serde(default)]
    n300: Option<u32>,
    #[serde(default)]
    n100: u32,
    #[serde(default)]
    n50: u32,
    #[serde(default)]
    ngeki: u32,
    #[serde(default)]
    nkatu: u32,
    #[serde(default)]
    nmiss: u32,
    #[serde(default)]
    combo: Option<u32>,
    #[serde(default)]
    score: u64,
    /// accuracy in % instead of hit counts (calculator)
    #[serde(default)]
    acc: Option<f64>,
}

#[derive(Serialize, Default)]
struct ScoreOutput {
    id: i64,
    pp: f64,
    stars: f64,
    aim: f64,
    speed: f64,
    acc: f64,
    fl: f64,
    reading: f64,
    max_combo: u32,
    error: Option<String>,
}

fn clean(x: f64) -> f64 {
    if x.is_finite() { (x * 1000.0).round() / 1000.0 } else { 0.0 }
}

fn out(id: i64, pp: f64, stars: f64) -> ScoreOutput {
    ScoreOutput { id, pp: clean(pp), stars: clean(stars), ..Default::default() }
}

fn fail(id: i64, msg: String) -> ScoreOutput {
    ScoreOutput { id, error: Some(msg), ..Default::default() }
}

fn osu_acc(s: &ScoreInput) -> f64 {
    let n300 = s.n300.unwrap_or(0);
    let total = n300 + s.n100 + s.n50 + s.nmiss;
    if total == 0 {
        return 100.0;
    }
    (300.0 * n300 as f64 + 100.0 * s.n100 as f64 + 50.0 * s.n50 as f64) / (300.0 * total as f64) * 100.0
}

fn mods_of(s: &ScoreInput) -> u32 {
    // like bancho: NC counts as DT
    if s.mods & NIGHTCORE != 0 { s.mods | DOUBLETIME } else { s.mods }
}

// ---------- bancho.py's formula (akatsuki-pp) ----------

fn calc_tsg(map: &akatsuki_pp::Beatmap, s: &ScoreInput) -> ScoreOutput {
    use akatsuki_pp::{AnyPP, GameMode, PerformanceAttributes};
    let mode = match s.mode {
        1 => GameMode::Taiko,
        2 => GameMode::Catch,
        3 => GameMode::Mania,
        _ => GameMode::Osu,
    };
    let mut pp = AnyPP::new(map).mode(mode).mods(mods_of(s)).n_misses(s.nmiss as usize);
    if let Some(c) = s.combo {
        pp = pp.combo(c as usize);
    }
    if let Some(a) = s.acc {
        pp = pp.accuracy(a);
    } else {
        if let Some(n) = s.n300 {
            pp = pp.n300(n as usize);
        }
        pp = pp
            .n100(s.n100 as usize)
            .n50(s.n50 as usize)
            .n_geki(s.ngeki as usize)
            .n_katu(s.nkatu as usize);
    }
    let r = pp.calculate();
    let mut o = out(s.id, r.pp(), r.stars());
    o.max_combo = r.max_combo() as u32;
    match r {
        PerformanceAttributes::Osu(a) => {
            o.aim = clean(a.pp_aim);
            o.speed = clean(a.pp_speed);
            o.acc = clean(a.pp_acc);
            o.fl = clean(a.pp_flashlight);
        }
        PerformanceAttributes::Taiko(a) => {
            o.speed = clean(a.pp_difficulty);
            o.acc = clean(a.pp_acc);
        }
        PerformanceAttributes::Mania(a) => {
            o.speed = clean(a.pp_difficulty);
        }
        PerformanceAttributes::Catch(_) => {}
    }
    o
}

// ---------- rosu-pp 4.0 (osu! Oct 2025) and pp-update (osu! Jul 2026) ----------
// The same code for both library versions: they differ only in the crate path
// and the pp_reading field, which exists only in the newer one.

macro_rules! rosu_calc {
    ($krate:ident, $map:expr, $s:expr, $reading:expr) => {{
        use $krate::{any::PerformanceAttributes, model::mode::GameMode, Performance};
        let s: &ScoreInput = $s;
        let mode = match s.mode {
            1 => GameMode::Taiko,
            2 => GameMode::Catch,
            3 => GameMode::Mania,
            _ => GameMode::Osu,
        };
        let mut perf = Performance::new($map)
            .mode_or_ignore(mode)
            .mods(mods_of(s))
            .lazer(false)
            .misses(s.nmiss);
        if let Some(c) = s.combo {
            perf = perf.combo(c);
        }
        if let Some(a) = s.acc {
            perf = perf.accuracy(a);
        } else {
            if let Some(n) = s.n300 {
                perf = perf.n300(n);
            }
            perf = perf.n100(s.n100).n50(s.n50).n_geki(s.ngeki).n_katu(s.nkatu);
        }
        if s.mode == 0 && s.score > 0 {
            // stable: estimating slider breaks uses the score
            perf = perf.legacy_total_score(s.score.min(u32::MAX as u64) as u32);
        }
        match perf.checked_calculate() {
            Err(_) => fail(s.id, "map flagged as suspicious".into()),
            Ok(r) => {
                let mut o = out(s.id, r.pp(), r.stars());
                o.max_combo = r.max_combo();
                match r {
                    PerformanceAttributes::Osu(a) => {
                        o.aim = clean(a.pp_aim);
                        o.speed = clean(a.pp_speed);
                        o.acc = clean(a.pp_acc);
                        o.fl = clean(a.pp_flashlight);
                        o.reading = clean($reading(&a));
                    }
                    PerformanceAttributes::Taiko(a) => {
                        o.speed = clean(a.pp_difficulty);
                        o.acc = clean(a.pp_acc);
                    }
                    PerformanceAttributes::Mania(a) => {
                        o.speed = clean(a.pp_difficulty);
                    }
                    PerformanceAttributes::Catch(_) => {}
                }
                o
            }
        }
    }};
}

fn calc_rosu4(map: &rosu_pp::Beatmap, s: &ScoreInput) -> ScoreOutput {
    rosu_calc!(rosu_pp, map, s, |_a: &rosu_pp::osu::OsuPerformanceAttributes| 0.0)
}

fn calc_rosu_next(map: &rosu_pp_next::Beatmap, s: &ScoreInput) -> ScoreOutput {
    rosu_calc!(rosu_pp_next, map, s, |a: &rosu_pp_next::osu::OsuPerformanceAttributes| a.pp_reading)
}

// ---------- older eras (osu!std only) ----------

fn calc_era(variant: &str, map: &rosu_pp::Beatmap, s: &ScoreInput) -> ScoreOutput {
    use rosu_pp_older as o;
    if s.mode != 0 {
        return fail(s.id, "this variant supports osu!std only".into());
    }
    let a = osu_acc(s);
    let m = mods_of(s);
    let combo = s.combo.unwrap_or(0);
    let n300 = s.n300.unwrap_or(0);
    macro_rules! old {
        ($module:ident, $acc:expr) => {{
            let r = o::$module::OsuPP::new(map)
                .mods(m).combo(combo).n300(n300).n100(s.n100)
                .n50(s.n50).misses(s.nmiss).accuracy($acc).calculate();
            let mut x = out(s.id, r.pp as f64, r.difficulty.stars as f64);
            x.aim = clean(r.pp_aim as f64);
            x.speed = clean(r.pp_speed as f64);
            x.acc = clean(r.pp_acc as f64);
            x
        }};
    }
    match variant {
        "osu_2014_may" => old!(osu_2014_may, a as f32),
        "osu_2014_jul" => old!(osu_2014_july, a as f32),
        "osu_2015_feb" => old!(osu_2015_february, a as f32),
        "osu_2015_apr" => old!(osu_2015_april, a as f32),
        "osu_2018" => old!(osu_2018, a as f32),
        "osu_2019" => old!(osu_2019, a as f32),
        "osu_2021_jan" => old!(osu_2021_january, a as f32),
        "osu_2021_jul" => old!(osu_2021_july, a as f32),
        "osu_2021_nov" => old!(osu_2021_november, a),
        "osu_2022" => {
            let r = o::osu_2022::OsuPP::new(map)
                .mods(m).combo(combo).n300(n300).n100(s.n100)
                .n50(s.n50).misses(s.nmiss).calculate();
            let mut x = out(s.id, r.pp, r.difficulty.stars);
            x.aim = clean(r.pp_aim);
            x.speed = clean(r.pp_speed);
            x.acc = clean(r.pp_acc);
            x.fl = clean(r.pp_flashlight);
            x
        }
        "osu_2024" => {
            let r = o::osu_2024::OsuPP::new(map)
                .mods(m).lazer(false).combo(combo).n300(n300).n100(s.n100)
                .n50(s.n50).misses(s.nmiss).calculate();
            let mut x = out(s.id, r.pp, r.difficulty.stars);
            x.aim = clean(r.pp_aim);
            x.speed = clean(r.pp_speed);
            x.acc = clean(r.pp_acc);
            x.fl = clean(r.pp_flashlight);
            x
        }
        "osu_2025_03" => match o::osu_2025::OsuPP::new(map)
            .mods(m).lazer(false).combo(combo).n300(n300).n100(s.n100)
            .n50(s.n50).misses(s.nmiss).calculate()
        {
            Ok(r) => {
                let mut x = out(s.id, r.pp, r.difficulty.stars);
                x.aim = clean(r.pp_aim);
                x.speed = clean(r.pp_speed);
                x.acc = clean(r.pp_acc);
                x.fl = clean(r.pp_flashlight);
                x
            }
            Err(e) => fail(s.id, format!("{e}")),
        },
        other => fail(s.id, format!("unknown variant {other}")),
    }
}

/// Calculates one score; if the library panics (e.g. a broken map) it returns an error instead of stopping everything.
fn guard(id: i64, f: impl FnOnce() -> ScoreOutput) -> ScoreOutput {
    match std::panic::catch_unwind(std::panic::AssertUnwindSafe(f)) {
        Ok(o) => o,
        Err(e) => {
            let msg = e.downcast_ref::<&str>().map(|s| s.to_string())
                .or_else(|| e.downcast_ref::<String>().cloned())
                .unwrap_or_else(|| "unknown error".into());
            fail(id, format!("calculator error: {msg}"))
        }
    }
}
// ---------- one map, all of its scores ----------

fn calc_map(variant: &str, path: &str, scores: &[&ScoreInput]) -> Vec<ScoreOutput> {
    let all_fail = |msg: String| scores.iter().map(|s| fail(s.id, msg.clone())).collect::<Vec<_>>();
    match variant {
        "tsg" => match akatsuki_pp::Beatmap::from_path(path) {
            Ok(map) => scores.iter().map(|s| guard(s.id, || calc_tsg(&map, s))).collect(),
            Err(e) => all_fail(format!("map: {e}")),
        },
        "osu_2026_07" => match rosu_pp_next::Beatmap::from_path(path) {
            Ok(map) => scores.iter().map(|s| guard(s.id, || calc_rosu_next(&map, s))).collect(),
            Err(e) => all_fail(format!("map: {e}")),
        },
        _ => match rosu_pp::Beatmap::from_path(path) {
            Ok(map) => {
                if variant == "osu_2025_10" {
                    scores.iter().map(|s| guard(s.id, || calc_rosu4(&map, s))).collect()
                } else {
                    scores.iter().map(|s| guard(s.id, || calc_era(variant, &map, s))).collect()
                }
            }
            Err(e) => all_fail(format!("map: {e}")),
        },
    }
}

fn main() {
    // a panic in the library is caught in guard(); keep stderr clean
    std::panic::set_hook(Box::new(|_| {}));
    if std::env::args().any(|a| a == "--variants") {
        let list: Vec<_> = VARIANTS
            .iter()
            .map(|(id, modes, info)| serde_json::json!({"id": id, "modes": modes, "info": info}))
            .collect();
        println!("{}", serde_json::to_string(&list).unwrap());
        return;
    }

    let mut buf = String::new();
    io::stdin().read_to_string(&mut buf).expect("stdin");
    let input: Input = match serde_json::from_str(&buf) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("JSON error: {e}");
            std::process::exit(1);
        }
    };
    let variant = input.variant.as_str();
    let Some((_, modes, _)) = VARIANTS.iter().find(|(id, _, _)| *id == variant) else {
        eprintln!("unknown variant: {variant}");
        std::process::exit(2);
    };

    // grouped by map: every .osu file is parsed once
    let mut by_map: HashMap<&str, Vec<&ScoreInput>> = HashMap::new();
    for s in &input.scores {
        by_map.entry(s.map.as_str()).or_default().push(s);
    }
    let groups: Vec<_> = by_map.into_iter().collect();

    let results: Vec<ScoreOutput> = groups
        .par_iter()
        .flat_map_iter(|(path, scores)| {
            let (ok, bad): (Vec<&ScoreInput>, Vec<&ScoreInput>) =
                scores.iter().partition(|s| modes.contains(&s.mode));
            let mut v = calc_map(variant, path, &ok);
            v.extend(bad.iter().map(|s| fail(s.id, "mode not supported by this variant".into())));
            v
        })
        .collect();

    // back to the input order
    let mut by_id: HashMap<i64, ScoreOutput> = results.into_iter().map(|r| (r.id, r)).collect();
    let ordered: Vec<ScoreOutput> = input
        .scores
        .iter()
        .map(|s| by_id.remove(&s.id).unwrap_or_else(|| fail(s.id, "no result".into())))
        .collect();
    println!("{}", serde_json::to_string(&ordered).unwrap());
}
