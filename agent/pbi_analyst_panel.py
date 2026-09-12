# `dataset` is injected by Power BI (or simulated in the notebook)
import os, json, hashlib, textwrap
from pathlib import Path
import pandas as pd
import matplotlib
try:
    get_ipython()                      # only defined inside Jupyter / IPython
except NameError:
    matplotlib.use("Agg")              # Power BI: headless backend
import matplotlib.pyplot as plt
plt.rcParams["text.parse_math"] = False     # "R$ 1,132,879" is text, not LaTeX
# %matplotlib inline
from dotenv import load_dotenv

PROJECT  = Path(r"C:\Users\manas\OneDrive\Desktop\Projects - AI + BI")
load_dotenv(PROJECT / ".env")            # absolute path: Power BI's cwd is not the project
CACHE    = PROJECT / "agent" / "panel_cache.json"
MODEL_ID = "models/gemini-3.6-flash"
PANEL_ALPHA = 0.36     # 0 = fully transparent, 1 = solid; 0.36 = 64% transparent

# ---- 1. shape the data ---------------------------------------------------
df = dataset.copy()
df["Month Start"] = pd.to_datetime(df["Month Start"])
for c in ["Revenue", "Orders", "AOV", "Avg Review Score", "Avg Delivery Days"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)

df = df.sort_values("Month Start").dropna(subset=["Revenue"])
df = df[df["Month Start"] < df["Month Start"].max()]        # drop partial tail month
category = str(df["Selected Category"].iloc[0])
state    = str(df["Selected State"].iloc[0])
recent   = df.tail(6).copy()
recent["rev_change_pct"] = (recent["Revenue"].pct_change() * 100).round(2)

# ---- 2. build the prompt (formatted for reading, not for math) -----------
table = recent[["Month Start", "Revenue", "Orders", "AOV",
                "Avg Review Score", "Avg Delivery Days", "rev_change_pct"]].copy()
table["Month Start"]       = table["Month Start"].dt.strftime("%b %Y")
table["Revenue"]           = table["Revenue"].map(lambda v: f"R$ {v:,.0f}")
table["Orders"]            = table["Orders"].map(lambda v: f"{v:,.0f}")
table["AOV"]               = table["AOV"].map(lambda v: f"R$ {v:,.2f}")
table["Avg Review Score"]  = table["Avg Review Score"].map(lambda v: f"{v:.2f} / 5")
table["Avg Delivery Days"] = table["Avg Delivery Days"].map(lambda v: f"{v:.1f} days")
table["rev_change_pct"]    = table["rev_change_pct"].map(
                                 lambda v: "—" if pd.isna(v) else f"{v:+.1f}%")
table = table.rename(columns={"rev_change_pct": "Revenue vs prior month"})

prompt = (
    f"Scope: category = {category}; state = {state}. "
    "Brazilian e-commerce marketplace; all money is BRL, shown as R$.\n"
    f"Last six complete months:\n\n{table.to_markdown(index=False)}\n\n"
    "Return: a headline (max 12 words); exactly 3 insights (max 20 words each, "
    "each citing a number from the table exactly as written); "
    "one recommendation (max 25 words). Use only numbers present in the table."
)

# ---- 3. cache keyed on the exact prompt + model --------------------------
key = hashlib.sha1((MODEL_ID + prompt).encode("utf-8")).hexdigest()
try:
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
except (json.JSONDecodeError, OSError):
    cache = {}                                  # empty or corrupt cache → start fresh

# ---- 4. Gemini, structured output ----------------------------------------
if key in cache:
    ai = cache[key]
else:
    try:
        from google import genai
        from google.genai import types
        from pydantic import BaseModel

        class Panel(BaseModel):
            headline: str
            insights: list[str]
            recommendation: str

        client = genai.Client()
        resp = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=("You are a senior e-commerce analyst. Plain English, "
                                    "no jargon, never invent numbers."),
                temperature=0.2,
                thinking_config=types.ThinkingConfig(
                    thinking_level=types.ThinkingLevel.MINIMAL
                ),
                max_output_tokens=1500,
                response_mime_type="application/json",
                response_schema=Panel,
            ),
        )
        fr = resp.candidates[0].finish_reason.name if resp.candidates else "NONE"
        if fr == "MAX_TOKENS":
            u = resp.usage_metadata
            raise RuntimeError(f"Truncated: {u.thoughts_token_count} thinking + "
                               f"{u.candidates_token_count} output tokens")
        ai = json.loads(resp.text)
        cache[key] = ai
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
    except Exception as e:                        # never let the visual go red
        ai = {"headline": "AI commentary unavailable",
              "insights": [f"{type(e).__name__}: {str(e)[:120]}"],
              "recommendation": "Check GOOGLE_API_KEY in .env, or the free-tier rate limit."}

# ---- 4. render: chart on top, commentary below ---------------------------
fig = plt.figure(figsize=(11, 6.5), dpi=110)
fig.patch.set_facecolor("white")
fig.patch.set_alpha(PANEL_ALPHA)
gs  = fig.add_gridspec(2, 1, height_ratios=[3, 2.2], hspace=0.35)

ax = fig.add_subplot(gs[0])
ax.set_facecolor((1, 1, 1, PANEL_ALPHA))
ax.plot(df["Month Start"], df["Revenue"] / 1e6, marker="o", linewidth=2)
ax.set_title(f"Monthly revenue — {category} · {state}", fontsize=13, loc="left")
ax.set_ylabel("R$ millions")
ax.grid(alpha=0.3)
ax.spines[["top", "right"]].set_visible(False)

tx = fig.add_subplot(gs[1])
tx.axis("off")
lines  = [ai["headline"], ""]
lines += ["•  " + textwrap.fill(s, 105, subsequent_indent="   ") for s in ai["insights"]]
lines += ["", "Recommended action: "
          + textwrap.fill(ai["recommendation"], 95, subsequent_indent="   ")]
tx.text(0, 1, "\n".join(lines), va="top", ha="left", fontsize=10.5, linespacing=1.5)
tx.text(0, -0.02, f"AI commentary · {MODEL_ID.split('/')[-1]}",
        fontsize=7.5, color="gray", va="top")

plt.show()
