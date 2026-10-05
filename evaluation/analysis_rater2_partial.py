"""Rater-2 partial analysis (7 author-recorded ratings). Read-only; prints JSON."""
import csv, json, math, sys
sys.path.insert(0, ".")
def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z*z/n; c = (p + z*z/(2*n))/d; h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return round(100*(c-h), 1), round(100*(c+h), 1)
r2 = {r["case_id"]: r["tier"] for r in csv.DictReader(open("evaluation/recovered/raters/rater2_user_supplied_corrected.csv"))}
mira = {r["case_id"]: r["mira_output"] for r in csv.DictReader(open("evaluation/recovered/mira_outputs.csv"))}
r1 = {r["case_key"].split("_")[0].upper(): r for r in csv.DictReader(open("evaluation/recovered/rater1_ratings_canonical.csv"))}
rows = []
for c, t in r2.items():
    m = mira[c]; mt = "parked" if m == "PARKED_CLARIFICATION" else m
    rows.append(dict(case=c, rater2=t, mira=mt, match=(mt == t), rater1_tier=r1[c]["rater1_tier"] or "(none)", rater1_provenance=r1[c]["tier_provenance"]))
k = sum(r["match"] for r in rows)
overlap = [r for r in rows if r["rater1_tier"] in ("emergency", "urgent", "routine")]
out = dict(n=len(rows), mira_vs_rater2_matches=k, ci95=wilson(k, len(rows)), rows=rows,
           rater1_rater2_overlap=dict(n=len(overlap), agree=sum(r["rater1_tier"] == r["rater2"] for r in overlap), cases=[r["case"] for r in overlap]))
print(json.dumps(out, indent=1))
