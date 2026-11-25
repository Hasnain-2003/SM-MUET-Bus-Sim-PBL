import json, re, copy
from docx import Document
from docx.shared import Pt, Inches, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

SRC = "/mnt/user-data/uploads/SQA_Assignment_by_22SW130.docx"
OUT = "/home/claude/MUET_Bus_PBL_22SW130.docx"
R = "/home/claude/repo/"
T = json.load(open(R + "results/tables.json"))
V = json.load(open(R + "results/verification.json"))
TUN = json.load(open(R + "results/tuned_params.json"))
FONT = "Times New Roman"


# ------------------------------------------------------------------ number helpers
def M(pk, k, m, d=1):
    return f"{T['main'][pk][k][m][0]:.{d}f}"


def MC(pk, k, m, d=1):
    a, h = T["main"][pk][k][m]
    return f"{a:.{d}f} ± {h:.{d}f}"


def PR(pk, k, m="eff_wait"):
    return abs(T["paired"][f"{pk}_{k}"][m]["rel"])


def FL(pk, k, n):
    return T["fleet"][pk][k][str(n)]


def DM(sc, k):
    return [r for r in T["demand"] if r["demand_scale"] == sc and r["policy"] == k][0]["eff_wait"]


def IC(p, k):
    return [r for r in T["incidents"] if r["incident_p"] == p and r["policy"] == k][0]["eff_wait"]


def SP(s, k, f="eff_wait"):
    return [r for r in T["split"] if abs(r["stc_share"] - s) < 1e-9 and r["policy"] == k][0][f]


def HD(pk, H, f="eff_wait"):
    return [r for r in T["headway"] if r["peak"] == pk and r["H"] == H][0][f]


# ------------------------------------------------------------------ open sample, edit cover, strip body
doc = Document(SRC)
body = doc.element.body
kids = list(body)
cut = None
for i, el in enumerate(kids):
    if el.tag == qn("w:p") and el.find(qn("w:pPr")) is not None and el.find(qn("w:pPr")).find(qn("w:sectPr")) is not None:
        cut = i
        break
for el in kids[cut + 1:-1]:           # keep cover section + final sectPr
    body.remove(el)


def set_run(p, old, new):
    for r in p.runs:
        if r.text == old:
            r.text = new
            return True
    return False


rep = {
    "SOFTWARE QUALITY ASSURANCE": "SIMULATION & MODELLING",
    "(SQA)": "(SM)",
    "A Study of Concepts, Process, and Formal Technical Review": "PBL: Modelling MUET Point Bus Scheduling and Queue Management",
    "Software Quality Assurance": "Simulation & Modelling",
    " What is SQA? | How does it Work? | How to Conduct an FTR?": " Queuing Theory | Discrete Event Simulation | Schedule Optimization",
    "Mr Arsalan Aftab": "Sir Umar Farooque",
    "August 23, 2026": "November 24, 2026",
}
done = set()
for p in doc.paragraphs[:cut + 1]:
    for old, new in rep.items():
        if set_run(p, old, new):
            done.add(old)
for t in doc.tables:
    for row in t.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for old, new in rep.items():
                    if set_run(p, old, new):
                        done.add(old)
assert done == set(rep), set(rep) - done

# header text of the report section
hp = doc.sections[-1].header.paragraphs[0]
hp.runs[0].text = "Simulation & Modelling (SM)  |  PBL: MUET Point Bus Scheduling and Queue Management"
for r in hp.runs[1:]:
    r.text = ""
# page numbers restart at 1 for the report

# heading styles (cover does not use them)
for name, size, bold, italic in (("Heading 1", 12, True, False), ("Heading 2", 11, False, True)):
    st = doc.styles[name]
    st.font.name = FONT; st.font.size = Pt(size); st.font.bold = bold; st.font.italic = italic
    st.font.color.rgb = RGBColor(0, 0, 0)
    rpr = st.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts"); rpr.append(rf)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(a), FONT)
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
        if rf.get(qn(a)) is not None:
            del rf.attrib[qn(a)]
    pf = st.paragraph_format
    pf.space_before = Pt(12 if name == "Heading 1" else 8); pf.space_after = Pt(4); pf.keep_with_next = True
    pf.left_indent = Inches(0); pf.first_line_indent = Inches(0)


# ------------------------------------------------------------------ writing helpers
def runs(p, text, size=11, bold=False, italic=False, font=FONT):
    text = text.replace('`', '')
    for tok in ([text] if font != FONT else re.split(r"(\*\*.+?\*\*|\*.+?\*|_\{[^}]*\}|\^\{[^}]*\})", text)):
        if not tok:
            continue
        b, i, sub, sup = bold, italic, False, False
        if tok.startswith("**"):
            tok, b = tok[2:-2], True
        elif tok.startswith("*"):
            tok, i = tok[1:-1], True
        elif tok.startswith("_{"):
            tok, sub = tok[2:-1], True
        elif tok.startswith("^{"):
            tok, sup = tok[2:-1], True
        r = p.add_run(tok)
        r.font.name = font; r.font.size = Pt(size); r.bold = b; r.italic = i
        r.font.subscript = sub; r.font.superscript = sup
        rpr = r._element.get_or_add_rPr()
        rf = rpr.find(qn("w:rFonts"))
        if rf is None:
            rf = OxmlElement("w:rFonts"); rpr.insert(0, rf)
        for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rf.set(qn(a), font)


def para(text, size=11, align="j", after=6, before=0, indent=True, bold=False, italic=False, keep=False):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(after); pf.space_before = Pt(before); pf.line_spacing = 1.08
    pf.first_line_indent = Inches(0.25) if indent else None
    pf.keep_with_next = keep
    p.alignment = {"j": WD_ALIGN_PARAGRAPH.JUSTIFY, "c": WD_ALIGN_PARAGRAPH.CENTER, "l": WD_ALIGN_PARAGRAPH.LEFT,
                   "r": WD_ALIGN_PARAGRAPH.RIGHT}[align]
    runs(p, text, size, bold, italic)
    return p


def h1(t):
    p = doc.add_paragraph(style="Heading 1"); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(t.upper()); r.font.name = FONT
    return p


def h2(t):
    p = doc.add_paragraph(style="Heading 2")
    r = p.add_run(t); r.font.name = FONT
    return p


_eq = [0]


def eq(text):
    _eq[0] += 1
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(2); pf.space_after = Pt(6)
    pf.tab_stops.add_tab_stop(Inches(3.25), WD_TAB_ALIGNMENT.CENTER)
    pf.tab_stops.add_tab_stop(Inches(6.5), WD_TAB_ALIGNMENT.RIGHT)
    runs(p, "\t" + text + f"\t({_eq[0]})", 11, italic=False)
    return p


_fig = [0]
_tab = [0]
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV"]


def fig(path, width, caption):
    _fig[0] += 1
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6); p.paragraph_format.space_after = Pt(2); p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(R + "figures/" + path, width=Inches(width))
    c = para(f"Fig. {_fig[0]}.  {caption}", size=9, align="c", after=10, indent=False)
    return _fig[0]


def shade(cell, color):
    tcPr = cell._element.get_or_add_tcPr()
    sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), color)
    tcPr.append(sh)


def borders(tbl):
    tblPr = tbl._element.tblPr
    b = OxmlElement("w:tblBorders")
    for edge, val in (("top", "single"), ("bottom", "single"), ("left", "nil"), ("right", "nil"), ("insideH", "single"), ("insideV", "nil")):
        e = OxmlElement(f"w:{edge}"); e.set(qn("w:val"), val)
        e.set(qn("w:sz"), "8" if edge in ("top", "bottom") else "2"); e.set(qn("w:space"), "0")
        e.set(qn("w:color"), "000000" if edge in ("top", "bottom") else "BFBFBF")
        b.append(e)
    tblPr.append(b)


def table(title, header, rows, widths, size=9, align=None, bold_first_col=False):
    _tab[0] += 1
    cap = para(f"TABLE {ROMAN[_tab[0]-1]}", size=9, align="c", after=0, before=8, indent=False, keep=True)
    for r in cap.runs: r.font.small_caps = True
    para(title.upper(), size=8.5, align="c", after=3, indent=False, keep=True)
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.autofit = False
    t.alignment = 1
    borders(t)
    tblW = t._element.tblPr.find(qn("w:tblW"))
    if tblW is None:
        tblW = OxmlElement("w:tblW"); t._element.tblPr.append(tblW)
    tblW.set(qn("w:type"), "dxa"); tblW.set(qn("w:w"), str(int(sum(widths) * 1440)))
    grid = t._element.find(qn("w:tblGrid"))
    for gc, w in zip(grid.findall(qn("w:gridCol")), widths):
        gc.set(qn("w:w"), str(int(w * 1440)))
    al = align or ["l"] * len(header)
    for ri, row in enumerate([header] + rows):
        tr = t.rows[ri]
        trPr = tr._tr.get_or_add_trPr()
        cs = OxmlElement("w:cantSplit"); trPr.append(cs)
        if ri == 0:
            th = OxmlElement("w:tblHeader"); trPr.append(th)
        for ci, val in enumerate(row):
            c = tr.cells[ci]; c.width = Inches(widths[ci])
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(1); p.paragraph_format.space_before = Pt(1)
            p.alignment = {"l": WD_ALIGN_PARAGRAPH.LEFT, "c": WD_ALIGN_PARAGRAPH.CENTER, "r": WD_ALIGN_PARAGRAPH.RIGHT}[al[ci]]
            runs(p, str(val), size, bold=(ri == 0 or (bold_first_col and ci == 0)))
            if ri == 0:
                shade(c, "E7EEF7")
    sp_ = doc.add_paragraph(); sp_.paragraph_format.space_after = Pt(4)
    for r in sp_.runs: r.font.size = Pt(4)
    return _tab[0]


def code(lines, size=8):
    for i, ln in enumerate(lines):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_after = Pt(0); pf.space_before = Pt(0); pf.left_indent = Inches(0.2); pf.right_indent = Inches(0.1)
        pf.keep_together = True
        if i < len(lines) - 1:
            pf.keep_with_next = True
        pPr = p._p.get_or_add_pPr()
        sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), "F2F2F2")
        pPr.append(sh)
        runs(p, ln if ln else " ", size, font="Courier New")
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


# =================================================================== TITLE BLOCK
para("Simulation and Optimisation of MUET Point Bus Scheduling and Queue Management", size=17, align="c", after=4, indent=False, bold=True)
para("Hasnain Aijaz Ansari (22SW130)", size=12, align="c", after=0, indent=False)
para("Department of Software Engineering, Mehran University of Engineering and Technology, Jamshoro", size=10, align="c", after=0, indent=False, italic=True)
para("Simulation & Modelling  |  PBL  |  Submitted to Sir Umar Farooque  |  November 24, 2026", size=10, align="c", after=10, indent=False, italic=True)

pm_over = M("PM", "S0", "over_pct", 0)
am_over = M("AM", "S0", "over_pct", 0)
para("**Abstract—**" + (
    "The MUET transport office runs a fleet of Points between Hyderabad and the Jamshoro campus, and in the 08:00–09:00 and 14:00–15:30 "
    "peaks students queue at the STC and Main Gate terminals for long periods while buses leave overloaded. We model the system as a "
    "bulk-service queue and implement it as a discrete event simulation in Python/SimPy. A static-timetable baseline, calibrated to reproduce "
    f"the symptoms in the problem statement, sends {pm_over}% of PM-peak trips out above the rated 60 passengers while buses stand idle next to "
    f"non-empty queues for about {M('PM','S0','idle_with_queue_busmin',0)} bus-minutes. Using 200 paired replications per peak we compare three "
    "dispatch policies on the same 24-bus fleet: demand-triggered release, a shared bus pool, and a predictive adaptive dispatcher (PAD) "
    f"that we propose. PAD removes over-capacity trips, lowers the effective passenger wait by {PR('PM','P3'):.0f}% (PM) and {PR('AM','P3'):.0f}% (AM), "
    f"and keeps both terminals' waits balanced even when demand is heavily skewed toward one terminal. In the PM peak a 20-bus fleet running PAD "
    f"does better than the current 24-bus static schedule. All demand and travel-time inputs are calibrated assumptions rather than field "
    "measurements; the report states them explicitly and shows where real data should replace them."), size=10, indent=False, after=4, italic=False)
para("**Index Terms—**discrete event simulation, queueing theory, bus dispatching, SimPy, what-if analysis, fleet utilisation.", size=10, indent=False, after=8, italic=True)

# =================================================================== I. INTRODUCTION
h1("I. Introduction")
para("Mehran University depends on its dedicated Points to move thousands of students, faculty and staff between the campus and Hyderabad "
     "every day. Outside the morning and early-afternoon peaks the service copes. Inside them it does not: queues build at the STC and Main Gate "
     "terminals, buses are frequently over capacity, and the timetable is static, so it cannot react to how many people actually turn up on a given "
     "day or to a bus that gets stuck in traffic. The transport administration has asked for data-driven scheduling improvements that do not "
     "involve buying more buses.")
para("This report answers the question posed in the problem statement: *how can the existing Point scheduling and queue-management system be "
     "modelled, simulated and analysed to find its bottlenecks, and which algorithmic scheduling changes minimise student waiting and maximise "
     "fleet utilisation?* We approach it in the order the learning objectives suggest. We first translate the physical system into a conceptual "
     "model (flowcharts and state-transition diagrams), then build a discrete event simulation of it, verify the code, reproduce the baseline "
     "symptoms, and finally run what-if experiments on alternative dispatch rules.")
para("The contributions of the work are: (a) a calibrated, parameterised simulation of the MUET peak-hour system with both an AM and a PM "
     "scenario; (b) a quantified diagnosis of four distinct bottlenecks in the static schedule; (c) three dispatch algorithms, including a "
     "predictive adaptive dispatcher, tuned fairly against each other on separate random seeds; (d) scenario analysis over fleet size, demand level, "
     "traffic incidents, timetable headway and demand split between terminals; and (e) a verification suite and open code so the results can be "
     "reproduced and the assumptions replaced with real counts.")
para("Section II analyses the problem and its constraints, Section III summarises the theory used, Section IV presents the conceptual model, "
     "Section V the implementation, and Section VI verification and validation. Sections VII to IX contain the baseline analysis, the proposed "
     "policies and the scenario results. Sections X to XII discuss trade-offs and limitations, give recommendations and conclude.")

# =================================================================== II. PROBLEM ANALYSIS
h1("II. Problem Analysis")
h2("A. Why this is a complex engineering problem")
para("The brief lists nine characteristics of a problem-based-learning problem. Table I records how each one shows up in the Point system, "
     "so that it is clear the task cannot be solved by a single formula or by simply adding a bus.")
table("PBL characteristics and how they appear in the MUET Point system",
      ["#", "Characteristic", "Where it appears in this problem"],
      [["1", "Depth of knowledge", "Queueing theory (bulk service), stochastic input modelling, discrete event simulation, output analysis."],
       ["2", "Conflicting requirements", "Short waits vs. safe loads; high utilisation vs. punctuality; average wait vs. fairness between terminals."],
       ["3", "Depth of analysis", "Transient, non-stationary demand; no closed-form answer, so replications, confidence intervals and paired tests are needed."],
       ["4", "Infrequent issues", "Breakdowns, road incidents and exam-day demand spikes that distort a single day but must be planned for."],
       ["5", "Beyond codes/standards", "No standard prescribes a dispatch rule for a campus shuttle; capacity and fairness limits are engineering judgements."],
       ["6", "Diverse stakeholders", "Students, drivers, transport office, faculty and administration want different things (Table II)."],
       ["7", "Interdependence", "Fleet size, headway, loading rule, terminal split and traffic all interact; changing one shifts the others."],
       ["8", "Significant consequences", "Missed classes, unsafe crowding, driver fatigue, and money spent on buses that may not be needed."],
       ["9", "Judgement", "Choosing the load cap, the wait–abandonment trade-off and which policy to recommend are judgement calls, not outputs of the model."]],
      [0.3, 1.5, 4.7], size=9, align=["c", "l", "l"])

h2("B. Stakeholders and conflicting requirements")
table("Stakeholders and what each one needs",
      ["Stakeholder", "Main need", "Possible conflict"],
      [["Students", "Short, predictable waits; a safe place on the bus", "Wants every bus to leave immediately, even if half empty"],
       ["Faculty and staff", "Reliable arrival before class", "Needs punctuality that crowding and delays undermine"],
       ["Drivers", "Safe loads, workable schedules, breaks", "Static slots and overloading raise pressure on them"],
       ["Transport office", "Use existing buses; rules that are easy to run", "Smarter dispatch needs a coordinator and information"],
       ["Administration", "Cost control, safety and liability", "Cheapest option (no buses) vs. safest option (strict load cap)"]],
      [1.3, 2.7, 2.5], size=9)
para("The conflicts are real. A load cap of 60 helps safety but reduces the number of students each trip can carry. Releasing buses early cuts "
     "waiting but sends out part-empty buses and shortens the fleet's capacity for the next wave. Moving buses between terminals balances queues but "
     "costs a four-minute dead-head. We therefore report several measures rather than a single score, and we keep the trade-offs visible in "
     "Section IX.")

h2("C. Requirements and constraints")
table("Constraints (C) and demands (D) identified for the study",
      ["ID", "Statement", "Source"],
      [["C1", "The existing fleet is fixed; no new buses may be purchased.", "Problem statement"],
       ["C2", "Two boarding terminals (STC, Main Gate); the route enters the campus through the Main Gate.", "Problem statement / assumption"],
       ["C3", "Rated capacity of a bus is 60 (45 seats plus 15 standing); the static regime tolerates up to 70.", "Assumption (see Table IV)"],
       ["C4", "Moving a free bus between terminals takes about 4 minutes.", "Assumption"],
       ["C5", "Round-trip time is uncertain (traffic, incidents); decisions cannot rely on knowing it.", "Problem statement"],
       ["C6", "Dispatch decisions must be simple enough for a human dispatcher with a phone to follow once a minute.", "Operational"],
       ["D1", "Minimise student waiting time (mean and tail).", "Problem statement"],
       ["D2", "Maximise fleet utilisation without breaking C3.", "Problem statement"],
       ["D3", "Eliminate over-capacity departures.", "Problem statement (“over-capacitated”)"],
       ["D4", "Treat the two terminals equitably.", "Stakeholder analysis"],
       ["D5", "Hold up when demand, fleet size or traffic differ from the planning values.", "Engineering judgement"]],
      [0.5, 4.5, 1.5], size=9, align=["c", "l", "l"])

# =================================================================== III. THEORY
h1("III. Theoretical Background")
h2("A. A terminal as a bulk-service queue")
para("Students arrive at a terminal over time, wait in a first-come-first-served line and are served in batches: a bus of capacity *K* loads up to "
     "*K* people and then disappears for a whole round trip. With *c* buses serving a terminal, each bus acts as a server whose service time is its "
     "cycle time. In Kendall-style notation this is an M(t)/G^{B}/c queue with batch service, time-varying arrivals and impatient customers. "
     "Exact results for such a queue are not available in closed form for non-stationary demand [3], which is the reason a simulation is needed. "
     "A simple analytical screen is still useful. For a demand wave of *D* students handled by *c* buses of capacity *K*, the wave load ratio is")
eq("ψ = D / (c · K)")
para("When ψ > 1 the terminal's buses cannot clear the wave in a single cycle and the surplus waits a full round trip (about 80 minutes here) "
     "for a bus to come back. This ratio is used in Section VII to show that the static 50/50 split of the fleet is mismatched with the demand.")

h2("B. Discrete event simulation")
para("In a discrete event simulation the system state changes only at event times, and the simulation clock jumps from one event to the next "
     "[1], [2]. SimPy [10] implements this with Python generator functions as processes that yield timeouts; we use one process per passenger "
     "stream, one per bus trip and one controller that wakes every minute. Because the demand window is a finite period (a lecture-change peak) "
     "and not a steady state, this is a *terminating* simulation: no warm-up is deleted, and every replication starts from the same initial "
     "condition and ends once the queues have drained.")

h2("C. Input models")
para("**Arrivals.** Passengers arrive as a non-homogeneous Poisson process with rate λ(t) shaped from Gaussian bumps (one around 08:30 for the AM peak, "
     "two around 14:08 and 15:02 for the PM peak, matching the lecture ends). Arrival times are generated by thinning [5]: candidate events are drawn "
     "at the maximum rate λ_{max} and each is kept with probability λ(t)/λ_{max}.")
para("**Round-trip time.** A trip lasts a lognormal time with mean 72 min and coefficient of variation 0.18, scaled by a peak congestion factor "
     "(1.10 AM, 1.05 PM), plus an incident delay with probability 0.12 and exponential mean 18 min. The lognormal parameters follow from")
eq("σ² = ln(1 + cv²),     μ = ln(m) − σ²/2")
para("**Patience.** A student who has waited longer than 20 + Exp(30) minutes (mean 50) gives up and finds other transport. We include reneging "
     "because otherwise a very long queue would be reported as a long wait for people who in reality never ride the bus.")

h2("D. Performance measures")
para("The mean and 90th-percentile wait of students who board describe the experience of those served, but they hide the students who leave. "
     "We therefore also report the share of students lost and a combined *effective wait*, in which each lost student counts as their time spent "
     "waiting plus a penalty *L* = 60 min:")
eq("W_{eff} = [ Σ_{boarded} w_{i} + Σ_{lost} (w_{j} + L) ] / N")
para("Other measures are the load factor (mean passengers per trip divided by 60), the percentage of trips departing above 60, fleet busy time "
     "(time on trips or dead-heading, as a share of fleet time in the window), and idle bus-minutes with a non-empty queue, which counts waste caused by "
     "dispatch rules. Fairness between terminals is measured by Jain's index [11],")
eq("J = (Σ x_{j})² / (n · Σ x_{j}²)")
para("applied to the two terminals' mean waits (J = 1 means equal waits). Little's law, L = λW [4], is used in Section VI as a consistency check.")

h2("E. Output analysis")
para("Each scenario is run with independent replications and reported as a mean with a 95% t-confidence interval. Policies are compared with "
     "*common random numbers*: replication *r* uses the same arrivals, patience values and the same luck for the k-th trip of bus *b* under every policy, "
     "so the difference between policies is estimated from paired differences, which have far smaller variance than independent runs.")

# =================================================================== IV. CONCEPTUAL MODEL
h1("IV. Conceptual Model")
h2("A. System description and boundary")
para("The model contains the two terminals, their waiting students, the fleet of Points and the dispatcher. The route itself is not modelled "
     "stop by stop; it is a random delay between leaving and returning to the Main Gate. Fig. 1 shows the flow of entities.")
fig("diag_system.png", 4.6, "Conceptual flow of the Point system as modelled: students arrive, queue by terminal, the dispatcher releases buses from the ready pool, and each bus runs a round trip and returns through the Main Gate.")

h2("B. Assumptions and inputs")
para("There are no measured MUET ridership logs available to us, so the values in Table IV are assumptions chosen to be realistic and then "
     "calibrated until the static baseline showed the symptoms the administration describes (long queues, over-capacity buses, buses idle while "
     "students wait). They are collected in a single configuration file so they can be replaced with measured values.")
table("Model inputs and assumptions",
      ["Item", "Value", "Remark"],
      [["Fleet", "24 buses, 12 based at each terminal (static regime)", "A1: assumed"],
       ["Capacity", "45 seats; rated 60; hard limit 70", "A2: standing room included"],
       ["Demand, PM (14:00–15:30)", "1,400 STC + 1,050 MG ≈ 2,450 students", "A3: calibrated; peaks at 14:08 and 15:02"],
       ["Demand, AM (08:00–09:00)", "980 STC + 730 MG ≈ 1,710 students", "A3: calibrated; peak ≈ 08:30"],
       ["Terminal meaning", "Boarding queue of one group of routes", "A4: same structure reused for AM and PM"],
       ["Round trip", "Lognormal, mean 72 min, cv 0.18; ×1.10 AM, ×1.05 PM", "A5: assumed"],
       ["Incidents", "p = 0.12 per trip, extra delay Exp(mean 18 min)", "A6: assumed"],
       ["Boarding time", "0.5 min + 0.04 min per passenger", "A7: ≈ 2.4 s per person"],
       ["Dead-head STC ↔ Main Gate", "4 min; buses enter campus at the Main Gate", "A8: assumed"],
       ["Patience", "20 min + Exp(mean 30 min)", "A9: nobody leaves before 20 min"],
       ["Dispatcher", "Wakes every 1 min; at most one release per terminal per tick", "A10: human-operable"],
       ["Initial fleet state", "PM: all buses parked at 14:00; AM: staggered returns", "A11: assumed"],
       ["Not modelled", "Individual stops, driver shifts, breakdowns that remove a bus", "Listed in Section X"]],
      [1.6, 3.0, 1.9], size=8.5)

h2("C. State-transition diagrams")
para("A bus is always in one of five states (Fig. 2). A free bus that is released to the terminal where it is parked starts boarding at once; "
     "one released to the other terminal first dead-heads for four minutes. If everybody has left during the dead-head the bus simply returns to the pool. "
     "In the static regime a returning bus goes back to its home terminal; in the pooled regimes it stays at the Main Gate, where the route enters the campus.")
fig("diag_bus_states.png", 3.9, "State-transition diagram of a bus.")
para("A passenger has only three outcomes (Fig. 3). The abandonment transition is what stops a long queue from producing unbounded waits and "
     "is the reason the effective-wait measure includes a penalty for lost students.")
fig("diag_pax_states.png", 6.2, "State-transition diagram of a passenger.")

# =================================================================== V. IMPLEMENTATION
h1("V. Simulation Implementation")
h2("A. Software structure")
para("The simulator is written in Python 3 with SimPy 4. The package `busqueue` has five small modules: *config* (all inputs and the demand shapes), "
     "*demand* (thinning), *model* (entities and processes), *policies* (the four dispatch rules) and *metrics* (summary statistics). "
     "Scripts at the top level run the experiments, tune the parameters, and make the figures. A passenger is an object with a state flag "
     "(waiting, boarded, abandoned); abandonments are handled with a deadline heap so a replication costs only a few tens of milliseconds.")
h2("B. Key code")
para("The controller process is the heartbeat of the model. Every minute it removes impatient students, updates the arrival-rate forecast "
     "used by PAD, logs the queues and hands control to the active policy:", after=3)
code(["def controller(self):",
      "    env, c = self.env, self.cfg",
      "    while True:",
      "        self.purge()                        # impatient students leave",
      "        for j in (STC, MG):                 # EWMA forecast of arrival rate",
      "            self.lam_hat[j] = (1-a)*self.lam_hat[j] + a*self.arr_tick[j]/c.tick",
      "            self.arr_tick[j] = 0",
      "        self.res.qlen.append((env.now, self.nq[STC], self.nq[MG]))",
      "        self.policy.decide(self)            # policy calls sim.dispatch(bus, j)",
      "        yield env.timeout(c.tick)"])
para("A released bus is a process of its own. It dead-heads if needed, loads first-come-first-served up to the policy's cap, spends boarding "
     "time, draws its round-trip time and finally rejoins the pool:", after=3)
code(["def run_trip(self, bus, j, t_order, cap, res):",
      "    if bus.loc != j:                        # dead-head to other terminal",
      "        yield env.timeout(c.repos_min); bus.loc = j",
      "    self.reserved[j] -= res; self.purge()",
      "    load = [p for p in self.board(j, cap)]  # FIFO, skip students who left",
      "    if not load:                            # everyone gave up meanwhile",
      "        self.bus_arrive_ready(bus); return",
      "    yield env.timeout(c.dwell_fixed + c.dwell_per_pax * len(load))",
      "    yield env.timeout(self.trip_time(bus, env.now))",
      "    bus.trips += 1",
      "    bus.loc = MG if self.policy.pooled else bus.home   # (+4 min if STC)",
      "    self.bus_arrive_ready(bus)"])
para("One detail needed care. A bus that is dead-heading has not yet picked anyone up, so on the next tick a naive dispatcher would see the same "
     "queue and send a second bus. The model therefore reserves seats for buses already on their way (`sim.qeff(j)` returns the queue net of "
     "reservations), a fix we added after reviewing the first version of the dispatcher.")

h2("C. Experimental set-up")
para("Every scenario uses independent replications with seeds 0 to 199 for the main comparison (AM and PM, four policies, 1,600 runs) and 0 to 99 for "
     "each point of the sensitivity studies. Policy parameters were tuned on separate seeds (1000 to 1029) and frozen before the evaluation, so that "
     "no policy is judged on the random numbers it was fitted to. The whole experiment suite takes about ten minutes on a single core.")

# =================================================================== VI. V&V
h1("VI. Verification and Validation")
para("Verification asks whether the code implements the conceptual model correctly; validation asks whether the model represents reality "
     "well enough for the decision at hand [9]. Six automated tests (pytest) address the first question and all pass (Table V).")
table("Verification tests",
      ["Test", "What it checks", "Outcome"],
      [["Conservation", "Every arrival is boarded, abandoned or still waiting (both peaks, all policies)", "Exact"],
       ["Little's law", "Area under the queue-length curve equals the sum of individual waits", f"Mean error {V['little_mean_err_pct']:.2f}% (max {V['little_max_err_pct']:.2f}%)"],
       ["Analytic batch wait", "With plentiful buses, constant λ = 3/min and batch K = 30, mean wait should be (K−1)/(2λ) = 4.83 min", f"Simulated {V['batch_sim']:.2f} min ({V['batch_n']:,} students)"],
       ["Deterministic trace", "130 students at t = 0.5, two buses, no randomness: loads 60, 60, 10; releases at t = 1, 84", "Matches hand calculation"],
       ["Capacity limits", "No PAD/P1 trip above 60; no static trip above 70", "Pass"],
       ["Reproducibility / CRN", "Same seed gives identical output; all policies see the same arrivals", "Pass"]],
      [1.3, 3.6, 1.6], size=8.5)
para("**Validation.** We do not have field data, so validation here is limited, and we say so plainly. We did three things. First, *face validity*: "
     "the baseline reproduces each symptom named in the problem statement (long queues at both terminals, buses over capacity, a schedule that does not "
     "adapt) and the model's structure was checked against how the Points operate. Second, *sensitivity checks* (Section IX) show that the "
     "qualitative conclusions do not hinge on a single input. Third, we propose a validation protocol for the transport office: count queue lengths "
     "at STC and Main Gate every five minutes and record bus departure times and loads for about two weeks, then compare the observed wait and load "
     "distributions with the simulated baseline using a two-sample Kolmogorov–Smirnov test, and re-calibrate the inputs in `config.py` until they agree.")

# =================================================================== VII. BASELINE
h1("VII. Baseline Analysis and Bottlenecks")
h2("A. The baseline (S0)")
para("The baseline models the current practice as we understand it. Each terminal owns half the fleet (12 buses) and may release one bus at fixed "
     "slots every 6 minutes. A slot is lost if no bus is parked at that moment, and a parked bus does not leave between slots. A bus takes whoever "
     "is waiting up to a physical limit of 70. The 6-minute headway is the cycle time (about 80 min) divided by the 12 buses at each terminal, rounded "
     "to a convenient figure. Fig. 4 shows the demand it faces.")
fig("fig_demand.png", 6.0, "Arrival rate at each terminal. The PM peak has two class-end waves; the AM peak is a single ramp toward the 09:00 lectures.")
para("Fig. 5 shows what the static schedule does with this demand. At STC the queue passes 400 students in both peaks (about 500 in the AM "
     "peak) and the PM queue has a second hump at the 15:00 wave. Main Gate queues are visibly smaller.")
fig("fig_baseline_queue.png", 6.2, "Mean number of students waiting under the static baseline (line) with the 10th–90th percentile band over 200 replications.")
para("Fig. 6 summarises the resource side. In the PM peak the fleet is busy for only " + M("PM", "S0", "fleet_busy_pct", 0) + "% of the window, "
     f"yet {pm_over}% of trips depart above the rated capacity and buses stand idle next to waiting students for {M('PM','S0','idle_with_queue_busmin',0)} bus-minutes. "
     f"The AM figures are {M('AM','S0','fleet_busy_pct',0)}% busy, {am_over}% over capacity and {M('AM','S0','idle_with_queue_busmin',0)} idle bus-minutes.")
fig("fig_baseline_diag.png", 6.2, "Baseline diagnostics: share of trips over rated capacity, fleet busy time and idle bus-minutes with a queue present (error bars: 95% CI).")

h2("B. Four bottlenecks")
dem_s = 1400 * 0.55 / 720
dem_m = 1050 * 0.55 / 720
para(f"**B1. A fixed split that does not match demand.** Demand is about 57% STC and 43% Main Gate, but each terminal owns half the fleet. "
     f"For the first PM wave (55% of the day's demand) the wave load ratio is ψ = {dem_s:.2f} at STC and {dem_m:.2f} at Main Gate, and in the AM peak "
     f"it is {980/720:.2f} and {730/720:.2f}. STC is overloaded while Main Gate has slack, and the mean waits show it: "
     f"{M('PM','S0','mean_wait_stc')} min at STC against {M('PM','S0','mean_wait_mg')} min at Main Gate in the PM, "
     f"{M('AM','S0','mean_wait_stc')} against {M('AM','S0','mean_wait_mg')} in the AM.")
para(f"**B2. Rigid slots leave buses idle.** Because a bus cannot leave outside its slot and a slot is wasted if no bus is there, the fleet is busy "
     f"only {M('PM','S0','fleet_busy_pct',0)}% of the PM window. With 12 buses parked at 14:00 and one release every 6 minutes per terminal, the last parked bus "
     f"would not leave until roughly an hour into the peak, and in the first half hour only about five buses per terminal have gone while the queue is still growing.")
para(f"**B3. Overloading as the pressure valve.** With nothing else to relieve the queue, drivers take up to 70. The mean load is "
     f"{float(M('PM','S0','load_factor',2)):.2f} of rated capacity in the PM peak and {M('AM','S0','over_pct',0)}% to {M('PM','S0','over_pct',0)}% of trips exceed 60. This is a safety "
     "problem, not only a comfort problem.")
para("**B4. No feedback.** The schedule does not look at queue length or waiting time and cannot adapt to a delayed bus or to a heavier day. In the "
     "simulation, two replications with the same average demand can produce quite different queues, and the static rule responds identically to both.")

# =================================================================== VIII. OPTIMISATION
h1("VIII. Proposed Scheduling Optimisations")
para("We evaluate three dispatch algorithms against the baseline, introducing one idea at a time so that its contribution can be measured. "
     "All three cap boarding at the rated 60 and none of them requires new buses.")
para("**P1: load-or-timeout.** A parked bus leaves terminal *j* as soon as the effective queue reaches a threshold θ, or somebody has waited longer than "
     "W_{max} and at least q_{min} students are present. The fleet is still split between terminals, so this isolates the effect of demand-triggered "
     "release and the load cap.")
para("**P2: pooled longest-queue-first.** Same trigger as P1, but the buses form one pool: a free bus goes to the eligible terminal with the longest queue, "
     "dead-heading across campus if necessary. This isolates the benefit of sharing the fleet.")
para("**P3: Predictive Adaptive Dispatch (PAD).** PAD is the pooled policy with two additions. The release threshold adapts to the forecast arrival rate, and "
     "the choice of terminal weighs the cost of dead-heading. The threshold is")
eq("θ_{j} = clip( min(θ_{full} − k(R − 1), λ̂_{j} · w_{hold}), θ_{min}, C )")
para("where R is the number of parked buses, C = 60, and λ̂ is an exponentially weighted moving average of the observed arrival rate,")
eq("λ̂_{j} ← (1 − α) λ̂_{j} + α · n_{j}(t) / Δt,     α = 0.2")
para("seeded with the historical average rate. During a lull the threshold falls, so buses are not held for a load that will take half an hour to build. "
     "The terminal for a free bus is chosen by the score")
eq("s_{j} = q_{j} / C + β · w_{j} / W_{max} − γ · d(b, j) / 4 min")
para("where q_{j} is the effective queue, w_{j} the head-of-line wait and d(b, j) the dead-head time of bus b to terminal j (0 or 4 minutes). "
     "The parameter k penalises holding buses when many are free; we included it because it seemed natural, and let the tuning decide. Fig. 7 gives the "
     "decision procedure executed at every tick, and the core of the policy is only a few lines of code:", after=3)
fig("diag_dispatch_flow.png", 3.6, "PAD dispatch procedure, executed at every one-minute tick.")
code(["def threshold(self, sim, j):",
      "    R = len(sim.pool[STC]) + len(sim.pool[MG])",
      "    th = min(self.theta_full - self.k * max(R - 1, 0), sim.lam_hat[j] * self.w_hold)",
      "    return max(self.th_min, min(self.cap, math.ceil(th)))",
      "",
      "def score(self, sim, bus, j):",
      "    move = self.cfg.repos_min if bus.loc != j else 0.0",
      "    return (sim.qeff(j) / self.cap",
      "            + self.beta * sim.oldest_wait(j) / self.w_max",
      "            - self.gamma * move / self.cfg.repos_min)"])
para("**Tuning.** Parameters of P1, P2 and PAD were selected by grid search on 30 training seeds, minimising the mean effective wait over both "
     "peaks (9 candidates each for P1 and P2, 162 for PAD). Giving the simpler policies the same treatment avoids flattering PAD. The selected values are "
     "in Table VI. Two results are worth noting: the optimum is flat (the top PAD settings differ by about 1%), and the tuning set k = 0, i.e. "
     "the idea of dispatching earlier when many buses are free did not help in this capacity-limited setting; the best behaviour is to fill buses "
     "to the rated capacity and use a long timeout as a safety net.")
table("Tuned parameters (frozen before evaluation)",
      ["Policy", "Parameters"],
      [["S0", "Headway H = 6 min (current practice); hard cap 70"],
       ["P1", f"θ = {TUN['P1']['theta']}, W_{{max}} = {TUN['P1']['w_max']} min, q_{{min}} = {TUN['P1']['q_min']}; cap 60"],
       ["P2", f"θ = {TUN['P2']['theta']}, W_{{max}} = {TUN['P2']['w_max']} min, q_{{min}} = {TUN['P2']['q_min']}; cap 60"],
       ["P3 (PAD)", f"θ_{{full}} = {TUN['P3']['theta_full']}, k = {TUN['P3']['k']}, w_{{hold}} = {TUN['P3']['w_hold']} min, θ_{{min}} = {TUN['P3']['th_min']}, "
                    f"W_{{max}} = {TUN['P3']['w_max']} min, β = 1, γ = {TUN['P3']['gamma']}; cap 60"]],
      [1.1, 5.4], size=9)

# =================================================================== IX. SCENARIOS
h1("IX. Scenario Analysis")
h2("A. Baseline versus optimised policies")
def mrows(pk):
    spec = [("Effective wait (min)", "eff_wait", 1), ("Mean wait, boarded (min)", "mean_wait", 1), ("90th-percentile wait (min)", "p90_wait", 1),
            ("Longest wait (min)", "max_wait", 1), ("Students lost (%)", "abandon_pct", 1), ("Trips above 60 pax (%)", "over_pct", 1),
            ("Load factor (of 60)", "load_factor", 2), ("Fleet busy (%)", "fleet_busy_pct", 1),
            ("Idle bus-min with queue", "idle_with_queue_busmin", 0), ("Mean total queue", "mean_queue", 0),
            ("Mean wait STC (min)", "mean_wait_stc", 1), ("Mean wait Main Gate (min)", "mean_wait_mg", 1), ("Jain index (terminals)", "jain_wait", 3)]
    return [[lab] + [MC(pk, k, m, d) for k in ("S0", "P1", "P2", "P3")] for lab, m, d in spec]
hdrs = ["Measure", "S0 static", "P1 load/timeout", "P2 pooled", "P3 PAD"]
table(f"PM peak (14:00–15:30), mean ± 95% CI over 200 replications", hdrs, mrows("PM"), [2.1, 1.1, 1.1, 1.1, 1.1], size=8.5, align=["l", "r", "r", "r", "r"])
table(f"AM peak (08:00–09:00), mean ± 95% CI over 200 replications", hdrs, mrows("AM"), [2.1, 1.1, 1.1, 1.1, 1.1], size=8.5, align=["l", "r", "r", "r", "r"])
para(f"All three dynamic policies improve on the baseline. In the PM peak the paired reduction in effective wait is {PR('PM','P1'):.0f}% for P1, "
     f"{PR('PM','P2'):.0f}% for P2 and {PR('PM','P3'):.0f}% for PAD; in the AM peak it is {PR('AM','P1'):.0f}%, {PR('AM','P2'):.0f}% and {PR('AM','P3'):.0f}%. "
     f"The intervals are tight (the 95% half-width of the PM PAD difference is {T['paired']['PM_P3']['eff_wait']['half']:.2f} min), so the ranking against the baseline "
     "is not in doubt. Over-capacity departures fall from "
     f"{pm_over}% and {am_over}% to zero, fleet busy time rises from {M('PM','S0','fleet_busy_pct',0)}% to {M('PM','P3','fleet_busy_pct',0)}% (PM) and from "
     f"{M('AM','S0','fleet_busy_pct',0)}% to {M('AM','P3','fleet_busy_pct',0)}% (AM), and idle bus-minutes beside a queue roughly halve.")
fig("fig_compare.png", 6.5, "Main performance measures by policy and peak (error bars: 95% CI over 200 replications).")
fig("fig_wait_cdf.png", 6.2, "Cumulative distribution of waiting time of students who boarded.")
para("Two nuances deserve honesty. First, the three dynamic policies are not equally good everywhere. P1 has the lowest PM effective wait "
     f"({M('PM','P1','eff_wait')} against {M('PM','P3','eff_wait')} min for PAD), but its two terminals are treated unequally: Jain index "
     f"{M('PM','P1','jain_wait',2)} (PM) and {M('AM','P1','jain_wait',2)} (AM) against {M('PM','P3','jain_wait',2)} and {M('AM','P3','jain_wait',2)} for PAD, with STC students "
     f"waiting nearly three times as long as Main Gate students in the AM peak ({M('AM','P1','mean_wait_stc')} against {M('AM','P1','mean_wait_mg')} min). Second, the "
     f"longest individual wait in the AM peak is higher under the dynamic policies ({M('AM','P3','max_wait',0)} min for PAD against {M('AM','S0','max_wait',0)} min for the baseline). "
     "This is the price of enforcing the 60-passenger cap: when a queue is longer than the buses available, some students at the back wait for the "
     "next bus instead of being squeezed onto the current one. The 90th-percentile wait still falls "
     f"({M('AM','S0','p90_wait')} to {M('AM','P3','p90_wait')} min), so the effect is limited to a small tail.")
para(f"PAD and P2 are almost identical on the averages ({M('PM','P2','eff_wait')} and {M('PM','P3','eff_wait')} min in the PM peak). The extra machinery of PAD, namely the "
     "forecast-based threshold and the dead-head-aware score, adds little under the planning demand. Its value lies elsewhere, as Section IX-D shows.")

h2("B. Queues and loads over time")
fig("fig_queue_s0_p3.png", 6.2, "Total number of students waiting, baseline versus PAD (mean and 10th–90th percentile band).")
para("Fig. 10 shows the effect on queue length: the static schedule builds a larger and longer queue because its buses leave late, and under PAD the "
     f"mean total queue over the window falls from {M('PM','S0','mean_queue',0)} to {M('PM','P3','mean_queue',0)} (PM) and from {M('AM','S0','mean_queue',0)} to {M('AM','P3','mean_queue',0)} (AM). "
     "Fig. 11 shows why the safety problem disappears: under S0 most trips leave with 61 to 70 on board, whereas under PAD almost every trip leaves at or just under 60.")
fig("fig_loads.png", 6.2, "Distribution of passengers per trip in the PM peak (dashed line: rated capacity of 60).")

h2("C. What-if: fleet size")
para("The brief asks for gains without buying buses. The reverse question is just as useful: how many buses does the better schedule save? "
     "Fig. 12 and Table IX vary the fleet from 16 to 28 buses.")
fig("fig_fleet.png", 6.2, "Effective wait versus fleet size. The dotted line is the baseline at the current 24 buses.")
rows = []
for n in (20, 22, 24, 26, 28):
    rows.append([str(n)] + [f"{FL('PM',k,n):.1f}" for k in ("S0", "P1", "P3")] + [f"{FL('AM',k,n):.1f}" for k in ("S0", "P1", "P3")])
table("Effective wait (min) versus fleet size (100 replications per cell)",
      ["Buses", "PM S0", "PM P1", "PM P3", "AM S0", "AM P1", "AM P3"], rows, [0.8, 0.95, 0.95, 0.95, 0.95, 0.95, 0.95], size=9,
      align=["c"] * 7)
para(f"In the PM peak, PAD with 20 buses ({FL('PM','P3',20):.1f} min) is better than the baseline with 24 ({FL('PM','S0',24):.1f} min), and with 22 buses "
     f"({FL('PM','P3',22):.1f} min) it is better than the baseline with 28 ({FL('PM','S0',28):.1f} min). In other words the same service quality can be delivered with "
     f"four to six fewer buses in service during the PM peak, which could be used for other routes or kept as spares. In the AM peak the picture is less generous: at 24 buses PAD "
     f"({FL('AM','P3',24):.1f} min) beats the baseline even with 28 ({FL('AM','S0',28):.1f} min), but at 22 buses it is about level with the baseline at 24 "
     f"({FL('AM','P3',22):.1f} against {FL('AM','S0',24):.1f} min), and with 20 buses or fewer the dynamic policies lose their edge "
     f"({FL('AM','P3',20):.1f} against {FL('AM','S0',20):.1f} min). With a very short fleet the cap of 60 costs more in throughput than rigid scheduling "
     "loses in idle time, which is a useful warning: the load cap should be a policy decision taken with the fleet size in mind, and not copied blindly.")

h2("D. What-if: demand split between the terminals")
para("The previous results assume the planning split of 57% STC. Demand shifts when a department moves, a hostel opens or exams change the "
     "timetable, so we varied the STC share of the same total demand from 35% to 80%.")
fig("fig_split.png", 6.2, "Effective wait and Jain fairness index versus the STC share of PM demand.")
para(f"The result separates the policies. P1, which keeps the fleet split, is the best choice only when the split is close to the planning value "
     f"({SP(0.45,'P1'):.1f} min at 45%) and collapses when demand is lopsided: {SP(0.70,'P1'):.1f} min at 70% and {SP(0.80,'P1'):.1f} min at 80% STC. "
     f"The pooled policies barely notice ({SP(0.80,'P3'):.1f} min for PAD at 80%, against {SP(0.57,'P3'):.1f} at 57%) and keep the Jain index at 0.98 or higher. "
     f"The baseline degrades like P1 ({SP(0.80,'S0'):.1f} min at 80%). This is the argument for pooling, and the reason we recommend a pooled policy even though P1 "
     "looks better at the planning split.")

h2("E. What-if: a better-tuned static timetable")
para("A fair objection is that the baseline headway of 6 minutes might simply be badly chosen. We therefore ran the static rule with headways from 2 to 8 minutes (Fig. 14).")
fig("fig_headway.png", 6.2, "Effective wait of the static timetable for different headways, compared with PAD.")
bestpm = min((HD("PM", H), H) for H in (2, 3, 4, 5, 6, 8))
bestam = min((HD("AM", H), H) for H in (2, 3, 4, 5, 6, 8))
para(f"Tuning helps: the best static headway is {bestpm[1]} min in the PM peak ({bestpm[0]:.1f} min effective wait) and {bestam[1]} min in the AM peak ({bestam[0]:.1f} min), "
     f"against {HD('PM',6):.1f} and {HD('AM',6):.1f} at 6 min. But PAD is still better ({M('PM','P3','eff_wait')} and {M('AM','P3','eff_wait')} min), by "
     f"{100*(bestpm[0]-float(M('PM','P3','eff_wait')))/bestpm[0]:.0f}% and {100*(bestam[0]-float(M('AM','P3','eff_wait')))/bestam[0]:.0f}%, and the tuned static rule still sends "
     f"{HD('PM',bestpm[1],'over_pct'):.0f}% (PM) and {HD('AM',bestam[1],'over_pct'):.0f}% (AM) of its trips out over capacity. A shorter headway is, in effect, a move toward "
     "releasing buses on demand, which supports the main finding. Retuning the timetable is a cheap first step but it does not remove the over-capacity problem or the imbalance.")

h2("F. What-if: demand level and traffic incidents")
rows = [[f"{sc:.1f}×", f"{DM(sc,'S0'):.1f}", f"{DM(sc,'P3'):.1f}", f"{100*(DM(sc,'S0')-DM(sc,'P3'))/DM(sc,'S0'):.0f}%"] for sc in (0.6, 0.8, 1.0, 1.2, 1.4)]
table("Effective wait (min), PM peak, versus demand level", ["Demand", "S0", "PAD", "PAD saving"], rows, [1.3, 1.3, 1.3, 1.3], size=9, align=["c"] * 4)
rows = [[f"{p:.2f}", f"{IC(p,'S0'):.1f}", f"{IC(p,'P3'):.1f}", f"{100*(IC(p,'S0')-IC(p,'P3'))/IC(p,'S0'):.0f}%"] for p in (0.0, 0.12, 0.25, 0.40)]
table("Effective wait (min), PM peak, versus probability of a trip incident", ["Incident prob.", "S0", "PAD", "PAD saving"], rows, [1.3, 1.3, 1.3, 1.3], size=9, align=["c"] * 4)
para(f"PAD saves between {min(100*(DM(sc,'S0')-DM(sc,'P3'))/DM(sc,'S0') for sc in (0.6,0.8,1.0,1.2,1.4)):.0f}% and {max(100*(DM(sc,'S0')-DM(sc,'P3'))/DM(sc,'S0') for sc in (0.6,0.8,1.0,1.2,1.4)):.0f}% of the effective wait from 0.6× to 1.4× the planning demand, so the benefit does not depend on the demand level chosen. "
     f"Incidents hurt both schedules, but PAD loses a little more in absolute terms (from {IC(0.0,'P3'):.1f} to {IC(0.40,'P3'):.1f} min as the incident probability goes from 0 to 0.40, "
     f"against {IC(0.0,'S0'):.1f} to {IC(0.40,'S0'):.1f} min for S0), because its buses are busier and have less slack, but it keeps an advantage of "
     f"{100*(IC(0.40,'S0')-IC(0.40,'P3'))/IC(0.40,'S0'):.0f}% even at 0.40.")

h2("G. What drives the improvement")
para("Putting the pieces together, the gain over the static timetable comes mainly from three things: releasing buses when students are waiting instead "
     "of at fixed slots, capping loads at the rated capacity, and (for equity and robustness) sharing the fleet between the terminals. The forecasting "
     "and cost-aware features of PAD contribute very little to the averages in our scenarios. We report this openly because it makes the practical "
     "recommendation simpler: the large gains do not need a sophisticated algorithm.")

# =================================================================== X. DISCUSSION
h1("X. Discussion, Judgement and Limitations")
h2("A. Judgement calls")
para("Several decisions in this study are judgements, not results. The 60-passenger cap is a safety choice and it costs capacity; we chose it because "
     "over-capacity buses are a stated problem. The 60-minute loss penalty in the effective wait means a student who gives up is treated as a failure of the "
     "service. We did not vary this penalty, so the mean wait and the share of students lost are also reported separately in Tables VII and VIII, and a reader can apply their own weighting. "
     "The choice to recommend a pooled policy over the numerically better P1 at the planning split rests on robustness (D5) and equity (D4), "
     "and another administrator could reasonably weigh these differently.")
h2("B. Consequences")
para("Overloaded buses are a safety and liability issue, and unreliable service pushes students toward private transport, which increases road "
     "traffic and costs. On the other side, a dispatcher who holds buses or moves them between terminals adds work for drivers: more dead-heading and less predictable departure "
     "times. The recommendations in Section XI therefore start with the cheapest and least intrusive changes.")
h2("C. Limitations and threats to validity")
para("(1) All demand and travel inputs are assumptions calibrated to the problem description, so absolute values (minutes, percentages) should be "
     "read as indicative; the comparison between policies is more trustworthy than any single number. (2) The route is represented by a random "
     "delay, not stop by stop; boarding at intermediate stops, which could reduce the effective capacity, is not modelled. (3) Breakdowns that remove a bus "
     "for the whole peak, driver shift limits, and students who choose a terminal based on queue length are not represented. (4) The AM peak reuses the terminal "
     "structure of the PM peak (assumption A4); if the real AM bottleneck lies at the Hyderabad pick-up stops, the policy logic transfers but "
     "the geometry and the 4-minute dead-head would need to be revised. (5) Tuning and evaluation used the same model, so the tuned parameters "
     "are optimal for the simulated world; a pilot on real buses is the real test.")

# =================================================================== XI. RECOMMENDATIONS
h1("XI. Recommendations")
para("Based on the experiments we recommend a phased introduction, ordered from cheapest to most involved.")
para(f"**Phase 1 (immediate, no tools).** Enforce the rated capacity of 60 and replace fixed departure slots with *load-or-timeout* release: a bus leaves "
     f"when it is full or when the first student in the line has waited about 20 minutes. This alone captures most of the gain (effective wait down "
     f"{PR('PM','P1'):.0f}% in the PM peak and {PR('AM','P1'):.0f}% in the AM peak) and eliminates over-capacity departures. It needs a dispatcher with a clipboard at each terminal.")
para(f"**Phase 2 (a few weeks).** Pool the fleet between STC and Main Gate. A single coordinator, reachable by phone or a group chat, tells a free bus where to go using the rule “longest queue "
     f"first unless the other terminal is nearly as bad and the bus is already there”. This makes the system tolerant of demand shifts: PAD stays "
     f"at about {SP(0.80,'P3'):.0f} minutes of effective wait even when 80% of demand is at STC, where the unpooled alternative reaches {SP(0.80,'P1'):.0f}.")
para("**Phase 3 (optional).** Add the PAD forecast (a moving average of arrivals) in a small spreadsheet or app. In our experiments this adds little to "
     "the averages, so it should be adopted only if it proves useful in the pilot.")
para("**Use of the saved buses.** The simulations suggest that, in the PM peak, four to six buses could be released from this duty without loss of service quality. "
     "We would not remove buses on the strength of a simulation alone: first measure real ridership for a few weeks, re-run the model with the measured inputs, "
     "and treat the spare buses as a reserve for breakdowns, which the model does not cover.")
para("**Data collection plan.** Count queue lengths at both terminals every five minutes for two weeks, and log bus departure times and loads. "
     "These measurements replace assumptions A3, A5, A6 and A9 and allow the validation test described in Section VI.")

# =================================================================== XII. CONCLUSION
h1("XII. Conclusion")
para(f"We modelled the MUET Point system as a bulk-service queue, implemented it as a verified SimPy simulation, and used it to diagnose four weaknesses of the static schedule: "
     f"a fleet split that does not match demand, rigid slots that leave buses idle, routine overloading ({pm_over}% of PM trips) and the lack of feedback from queue length. "
     f"Three dispatch policies that need no new buses reduce the effective student wait by {PR('PM','P3'):.0f}–{PR('PM','P1'):.0f}% in the PM peak and by {PR('AM','P1'):.0f}–{PR('AM','P3'):.0f}% in the "
     f"AM peak, remove over-capacity trips and raise fleet utilisation. The pooled policies, including our predictive adaptive dispatcher, are also fair to both terminals "
     f"and robust to lopsided demand, while the simplest policy (P1) is best only when demand matches the planning split. The main limitation is that inputs are calibrated "
     "assumptions; the first follow-up should be to collect two weeks of real counts, validate the model and re-run the experiments, which the provided code is designed to make easy.")

# =================================================================== REFERENCES
h1("References")
refs = [
    "J. Banks, J. S. Carson II, B. L. Nelson and D. M. Nicol, *Discrete-Event System Simulation*, 5th ed. Upper Saddle River, NJ, USA: Pearson, 2010.",
    "A. M. Law, *Simulation Modeling and Analysis*, 5th ed. New York, NY, USA: McGraw-Hill, 2015.",
    "D. Gross, J. F. Shortle, J. M. Thompson and C. M. Harris, *Fundamentals of Queueing Theory*, 4th ed. Hoboken, NJ, USA: Wiley, 2008.",
    "J. D. C. Little, “A proof for the queuing formula: L = λW,” *Operations Research*, vol. 9, no. 3, pp. 383–387, 1961.",
    "P. A. W. Lewis and G. S. Shedler, “Simulation of nonhomogeneous Poisson processes by thinning,” *Naval Research Logistics Quarterly*, vol. 26, no. 3, pp. 403–413, 1979.",
    "V. R. Vuchic, *Urban Transit: Operations, Planning and Economics*. Hoboken, NJ, USA: Wiley, 2005.",
    "G. F. Newell and R. B. Potts, “Maintaining a bus schedule,” in *Proc. 2nd Australian Road Research Board Conf.*, vol. 2, 1964, pp. 388–393.",
    "G. Osuna and G. F. Newell, “Control strategies for an idealized public transportation system,” *Transportation Science*, vol. 6, no. 1, pp. 52–72, 1972.",
    "R. G. Sargent, “Verification and validation of simulation models,” *Journal of Simulation*, vol. 7, no. 1, pp. 12–24, 2013.",
    "SimPy Team, “SimPy: Discrete event simulation for Python,” documentation, https://simpy.readthedocs.io.",
    "R. Jain, D.-M. Chiu and W. Hawe, “A quantitative measure of fairness and discrimination for resource allocation in shared computer systems,” Digital Equipment Corp., Tech. Rep. DEC-TR-301, 1984.",
]
for i, r in enumerate(refs, 1):
    p = para(f"[{i}]  " + r, size=9.5, align="j", after=2, indent=False)
    p.paragraph_format.left_indent = Inches(0.35); p.paragraph_format.first_line_indent = Inches(-0.35)

# =================================================================== APPENDICES
h1("Appendix A. Source Code and How to Run It")
para("The code is organised as a small Python package with a README.md that gives the full instructions. In short:", after=3)
code(["muet-bus-sim/",
      "  README.md   requirements.txt",
      "  src/busqueue/   config.py  demand.py  model.py  policies.py  metrics.py",
      "  tests/test_model.py",
      "  run_experiments.py   tune.py   analyze.py   verify_numbers.py",
      "  diagrams/ (Graphviz sources)   figures/   results/ (CSV, JSON)"])
code(["pip install -r requirements.txt",
      "export PYTHONPATH=src            # Windows PowerShell: $env:PYTHONPATH='src'",
      "pytest -q                        # six verification tests",
      "python tune.py                   # parameter search on training seeds",
      "python run_experiments.py        # all scenarios (~10 min on one core)",
      "python analyze.py                # figures and tables"])
h1("Appendix B. Mapping to the Assessment Rubrics")
table("Where each rubric item and learning objective is addressed",
      ["Item", "Where addressed"],
      [["R1 Constraints, requirements, demands", "Section II (Tables I–III), assumptions in Section IV-B (Table IV)"],
       ["R2 Originality / contribution", "PAD dispatcher (Section VIII); fair tuning of all policies; fleet-equivalence, demand-split and static-retuning analyses (Section IX)"],
       ["R3 Engineering knowledge and standards", "Queueing theory, NHPP thinning, CRN and paired analysis (Section III); verification suite (Section VI); IEEE report format and references"],
       ["R4 Efficiency of the solution", "Section IX: waits, utilisation, over-capacity and fleet savings with 95% confidence intervals"],
       ["Queueing theory and DES", "Sections III and V"],
       ["Conceptual model (state diagrams, flowcharts)", "Section IV (Figs. 1–3) and Fig. 7"],
       ["Functioning simulation in an industry tool", "Python/SimPy code, Appendix A"],
       ["What-if scenario analysis", "Section IX-C to IX-F"]],
      [2.4, 4.1], size=9)

doc.core_properties.title = "PBL: Simulation and Optimisation of MUET Point Bus Scheduling and Queue Management"
doc.core_properties.author = "Hasnain Aijaz Ansari"
doc.save(OUT)
print("saved", OUT, "figs", _fig[0], "tables", _tab[0])
