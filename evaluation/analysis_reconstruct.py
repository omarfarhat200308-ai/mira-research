"""
Reproducible reconstruction of the Rater-1 analyses. Read-only on all inputs.

Inputs (never modified):
  evaluation/recovered/raters/Omar_bhaiyas_project.xlsx.ORIGINAL   (Rater-1 workbook, copied byte-identically)
  eval/results/final/raw_results.jsonl                              (recovered outputs)
  logs/2026-09-11.jsonl                                             (verbatim agent logs; for stage reached)
  eval/cases_30.py, docs/clinical_review_worksheet.csv

Outputs (DERIVED, regenerated each run):
  evaluation/recovered/rater1_ratings_canonical.csv
  evaluation/ANALYSIS_A_published_rule.csv
  evaluation/ANALYSIS_B_consistent_rule.csv
  evaluation/PARKED_CASE_AUDIT.csv
  evaluation/analysis_summary.json

Run:  .venv/bin/python evaluation/analysis_reconstruct.py     (from ~/mira)
"""
import collections, csv, json, math, re, sys, zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, ".")
from eval.cases_30 import CASES  # noqa: E402

M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
TIERS = ("emergency", "urgent", "routine")
WB = "evaluation/recovered/raters/Omar_bhaiyas_project.xlsx.ORIGINAL"


def read_workbook(path):
    z = zipfile.ZipFile(path)
    ss = [''.join(t.text or '' for t in si.iter(M + 't')) for si in ET.fromstring(z.read('xl/sharedStrings.xml')).iter(M + 'si')]
    rows = []
    for row in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).iter(M + 'row'):
        d = {}
        for c in row.findall(M + 'c'):
            col = re.match(r'[A-Z]+', c.get('r')).group()
            v = c.find(M + 'v')
            if v is not None:
                d[col] = ss[int(v.text)] if c.get('t') == 's' else v.text
        rows.append(d)
    return rows


def wilson(k, n, z=1.96):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def mira_tier(rec):
    """tier | 'parked' (awaiting_clarification) ; failsafe-degraded keeps its urgent tier but is flagged."""
    if rec["pipeline_status"] == "awaiting_clarification":
        return "parked"
    return rec["actual_final_triage"] or "none"


# ---------- load ----------
wb = read_workbook(WB)
hdr = wb[0]
docs = {r["case_key"]: r for r in csv.DictReader(open("docs/clinical_review_worksheet.csv", encoding="utf-8"))}
final = {}
for l in open("eval/results/final/raw_results.jsonl"):
    r = json.loads(l); final[r["key"]] = r
meta = {c.key: c for c in CASES}
agents = collections.defaultdict(list)
for l in open("logs/2026-09-11.jsonl"):
    a = json.loads(l); agents[a["case_id"]].append(a)

# ---------- Rater-1 canonical table with provenance ----------
TW = re.compile(r"(emergency|urgent|routine)", re.I)
canon = []
for d in wb[1:]:
    k = d["A"]
    exp = meta[k].expected_final_triage.value if meta[k].expected_final_triage else "park"
    I_orig = docs[k]["MIRA_decision_path"] or ""
    I_cell = d.get("I", "")
    I_edit = I_cell if I_cell != I_orig else ""
    J, K, L = d.get("J", ""), d.get("K", ""), d.get("L", "")
    raw = " || ".join(x for x in [f"J={J}" if J else "", f"K={K}" if K else "", f"L={L}" if L else "",
                                  f"I(edited, wrong column)={I_edit}" if I_edit else ""] if x)
    explicit = None; where = ""
    for name, cell in (("K", K), ("I", I_edit), ("J", J), ("L", L)):
        m = TW.search(cell or "")
        if m:
            explicit, where = m.group(1).lower(), name; break
    j = J.strip().lower()
    if explicit:
        tier, prov = explicit, "DIRECTLY WRITTEN"
        note = f"tier word in column {where}" + ("; typed in the MIRA_decision_path column" if where == "I" else "")
    elif j in ("agree", "correct") and exp in TIERS:
        tier, prov = exp, "INFERRED FROM TEXT"
        note = f"'{j}' read as agreement with the author-assigned tier; could instead refer to MIRA's output"
    elif "need more" in K.lower():
        tier, prov = "need_more_info", "DIRECTLY WRITTEN"; note = "not a triage tier"
    elif j == "not agree":
        tier, prov = "", "UNVERIFIED"; note = "'not agree' is not a tier; no replacement tier written"
    else:
        tier, prov = "", "UNVERIFIED"; note = "row blank in recovered workbook"
    canon.append(dict(case_key=k, group=d["B"], author_expected=exp,
                      mira_cell_in_workbook=d.get("H", ""), rater1_raw_entries=raw,
                      rater1_tier=tier, tier_provenance=prov, note=note))
with open("evaluation/recovered/rater1_ratings_canonical.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(canon[0].keys())); w.writeheader(); w.writerows(canon)
can = {r["case_key"]: r for r in canon}

# ---------- Analysis A: published-rule reconstruction ----------
cases = [c.key for c in CASES]
non_b2 = [k for k in cases if k != "b2_reduced_fetal_movement"]
NODEC_EXCLUDED_AS_MATCH = {"d2_child_fever_well", "d3_child_diarrhea_no_dehydration", "d4_adult_sprain"}
MISMATCH = {"c1_child_fast_breathing", "d5_adult_sore_throat", "g1_elderly_chest_pain_alone"}
OVERTRIAGE_OK = {"c6_infant_persistent_fever"}
A = []
for k in non_b2:
    t = mira_tier(final[k]); g = meta[k].group
    if k in OVERTRIAGE_OK: bucket, why = "acceptable_over_triage", "paper reports C6 separately ('1/29')"
    elif k in MISMATCH: bucket, why = "tier_mismatch", "decided tier differs from rater/expected tier"
    elif t == "parked" and g != "F" and k not in NODEC_EXCLUDED_AS_MATCH: bucket, why = "no_decision", "parked, non-F"
    else:
        bucket = "match"
        why = {"d2_child_fever_well": "COUNTED AS MATCH although MIRA parked (rater wrote 'agree'/'routine')",
               "d3_child_diarrhea_no_dehydration": "COUNTED AS MATCH although MIRA parked (rater wrote 'agree'/'routine')",
               "d4_adult_sprain": "COUNTED AS MATCH although MIRA parked (rater wrote 'agree'/'routine')",
               "f1_vague_sick_since_morning": "parked appropriately (group F; rater 'need more information')",
               "f2_missing_severity": "parked appropriately (group F; rater 'need more information')",
               "b1_severe_weakness_breathing": "COUNTED AS MATCH although rater row is BLANK (MIRA emergency = author-expected emergency)"}.get(k, "decided tier equals rater/expected tier")
    nd_tier = ""
    if bucket == "no_decision":
        rt = can[k]["rater1_tier"]
        nd_tier = rt if rt in TIERS else meta[k].expected_final_triage.value  # fallback to author label when rater blank
    A.append(dict(case_key=k, group=g, mira=t, author_expected=can[k]["author_expected"], rater1_tier=can[k]["rater1_tier"],
                  rater1_provenance=can[k]["tier_provenance"], bucket=bucket, reason=why, correct_tier_used_for_split=nd_tier))
with open("evaluation/ANALYSIS_A_published_rule.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(A[0].keys())); w.writeheader(); w.writerows(A)
cA = collections.Counter(r["bucket"] for r in A)
split = collections.Counter(r["correct_tier_used_for_split"] for r in A if r["bucket"] == "no_decision")
a_summary = dict(denominator=len(A), match=cA["match"], no_decision=cA["no_decision"], mismatch=cA["tier_mismatch"],
                 acceptable_over_triage=cA["acceptable_over_triage"], nodecision_split=dict(split),
                 ci_match=wilson(cA["match"], len(A)), ci_nodec=wilson(cA["no_decision"], len(A)))

# ---------- Analysis B: one internally consistent rule ----------
def analysis_b(include_inferred=True):
    rows = []
    for k in cases:
        c = can[k]; t = mira_tier(final[k])
        usable = c["rater1_tier"] in TIERS and (include_inferred or c["tier_provenance"] == "DIRECTLY WRITTEN")
        if not usable:
            rows.append(dict(case_key=k, in_denominator=False, mira=t, rater1_tier=c["rater1_tier"], provenance=c["tier_provenance"], match="", exclusion_reason=c["note"] if c["tier_provenance"] != "INFERRED FROM TEXT" else "inferred tier excluded in direct-only sensitivity")); continue
        rows.append(dict(case_key=k, in_denominator=True, mira=t, rater1_tier=c["rater1_tier"], provenance=c["tier_provenance"], match=(t == c["rater1_tier"]), exclusion_reason=""))
    return rows
B = analysis_b(True); Bd = analysis_b(False)
with open("evaluation/ANALYSIS_B_consistent_rule.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(B[0].keys())); w.writeheader(); w.writerows(B)
def summ(rows):
    den = [r for r in rows if r["in_denominator"]]; k = sum(1 for r in den if r["match"]); n = len(den)
    return dict(n=n, matches=k, parked=sum(1 for r in den if r["mira"] == "parked"), ci=wilson(k, n),
                match_ids=[r["case_key"] for r in den if r["match"]])
b_all, b_direct = summ(B), summ(Bd)

# ---------- INDEPENDENT recount (separate code path: raw xlsx + raw_results only; no canon/mira_tier helpers) ----------
def independent_count():
    rows = read_workbook(WB)[1:]
    tier_by = {}
    for d in rows:
        k = d["A"]; txt = " ".join(d.get(c, "") for c in "KIJL")
        # original repo CSV decides whether column I was pre-filled
        pre = docs[k]["MIRA_decision_path"] or ""
        if d.get("I", "") == pre: txt = " ".join(d.get(c, "") for c in "KJL")
        low = txt.lower(); found = [t for t in TIERS if t in low]
        if found: tier_by[k] = found[0]
        elif d.get("J", "").lower() in ("agree", "correct"):
            tier_by[k] = meta[k].expected_final_triage.value
    n = k_ = 0
    for l in open("eval/results/final/raw_results.jsonl"):
        r = json.loads(l)
        if r["key"] not in tier_by: continue
        n += 1
        if r["pipeline_status"] != "awaiting_clarification" and r["actual_final_triage"] == tier_by[r["key"]]: k_ += 1
    return n, k_
ind_n, ind_k = independent_count()

# ---------- Parked-case audit ----------
P = []
for k in cases:
    r = final[k]
    if r["pipeline_status"] != "awaiting_clarification": continue
    fc = r["full_case"]; calls = agents.get(r["case_id"], [])
    stages = [a["agent_name"] for a in calls if a["status"] == "ok"]
    exp_rule = meta[k].expected_rule_id if hasattr(meta[k], "expected_rule_id") else ""
    P.append(dict(case_key=k, group=meta[k].group, author_expected=can[k]["author_expected"],
        rater1_tier=can[k]["rater1_tier"], rater1_provenance=can[k]["tier_provenance"],
        stages_completed="+".join(stages) or "none", reached_triage=("triage" in stages),
        red_flag_rules_evaluated=("triage" in stages), expected_rule_id=exp_rule or "",
        intake_status=r["intake_status"], clarification_rounds_so_far=len(fc.get("clarification_history") or []),
        pending_question=(fc.get("pending_clarifying_question") or ""),
        patient_facing_reply_present=bool((r.get("patient_facing_reply") or "").strip()),
        next_steps_present=bool((fc.get("next_steps") or "").strip()) or bool(fc.get("next_steps_bullets")),
        warning_signs_present=bool(fc.get("warning_signs")),
        referral_or_facility_present=bool((fc.get("facility_type") or "").strip()),
        final_triage=fc.get("final_triage"), doctor_handoff_status=fc.get("doctor_handoff_status"),
        park_reason=('missing_sex' if re.search(r'(?i)\b(sex|male|female)\b', fc.get('pending_clarifying_question') or '') else 'missing_duration_severity_or_other'),
        message_content_sent_by_webhook="clarifying question only (mira/webhook.py L187-189, L251-253)",
        safety_or_referral_message_sent=False))
with open("evaluation/PARKED_CASE_AUDIT.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(P[0].keys())); w.writeheader(); w.writerows(P)

summary = dict(analysis_A=a_summary, analysis_B_all_usable=b_all, analysis_B_direct_only=b_direct,
               independent_recount=dict(n=ind_n, matches=ind_k, agrees_with_B_all_usable=(ind_n, ind_k) == (b_all["n"], b_all["matches"])),
               parked=dict(n=len(P), reached_triage=sum(r["reached_triage"] for r in P),
                           with_reply=sum(r["patient_facing_reply_present"] for r in P),
                           with_next_steps=sum(r["next_steps_present"] for r in P),
                           with_facility=sum(r["referral_or_facility_present"] for r in P),
                           stage_sets=dict(collections.Counter(r["stages_completed"] for r in P)),
                           park_reasons=dict(collections.Counter(r["park_reason"] for r in P))),
               provenance_counts=dict(collections.Counter(r["tier_provenance"] for r in canon)))
json.dump(summary, open("evaluation/analysis_summary.json", "w"), indent=2, default=str)
print(json.dumps(summary, indent=2, default=str))
