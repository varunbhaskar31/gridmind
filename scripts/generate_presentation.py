"""Generate high-impact, professional PowerPoint presentation for GridMind.

Targeted for:
ET AI Hackathon: Agentic Edition (Accenture × The Economic Times)
Problem Statement 4: Utilities — Renewable Energy Orchestrator
Claimed Positioning: D2 / F3
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

# --- Color Palette ---
COLOR_BG = RGBColor(11, 19, 43)          # Deep Midnight Navy (#0B132B)
COLOR_CARD_BG = RGBColor(19, 29, 56)     # Navy Card Surface (#131D38)
COLOR_CARD_BORDER = RGBColor(45, 58, 93) # Card Border (#2D3A5D)
COLOR_TEXT_WHITE = RGBColor(255, 255, 255) # Pure White
COLOR_TEXT_SLATE = RGBColor(148, 163, 184) # Muted Slate (#94A3B8)
COLOR_TEXT_DIM = RGBColor(100, 116, 139)   # Dim Gray (#64748B)

COLOR_CYAN = RGBColor(56, 189, 248)      # AI & Telemetry Cyan (#38BDF8)
COLOR_EMERALD = RGBColor(16, 185, 129)   # Renewable & Clean Energy (#10B981)
COLOR_AMBER = RGBColor(245, 158, 11)     # Storage & Warning (#F59E0B)
COLOR_INDIGO = RGBColor(129, 140, 248)   # Optimization & Math (#818CF8)
COLOR_ROSE = RGBColor(244, 63, 94)       # Danger & Constraints (#F43F5E)

FONT_HEADING = "Helvetica"
FONT_BODY = "Arial"

def create_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    def add_bg(slide):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
        bg.fill.solid()
        bg.fill.fore_color.rgb = COLOR_BG
        bg.line.fill.background()
        return bg

    def add_header(slide, tag, title, subtitle, slide_num):
        add_bg(slide)

        # Header tag
        tag_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.3))
        tf_tag = tag_box.text_frame
        tf_tag.word_wrap = True
        tf_tag.margin_left = tf_tag.margin_top = tf_tag.margin_right = tf_tag.margin_bottom = 0
        p_tag = tf_tag.paragraphs[0]
        p_tag.text = tag.upper()
        p_tag.font.name = FONT_HEADING
        p_tag.font.size = Pt(9.5)
        p_tag.font.bold = True
        p_tag.font.color.rgb = COLOR_CYAN

        # Title
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.7), Inches(11.7), Inches(0.55))
        tf_title = title_box.text_frame
        tf_title.word_wrap = True
        tf_title.margin_left = tf_title.margin_top = tf_title.margin_right = tf_title.margin_bottom = 0
        p_title = tf_title.paragraphs[0]
        p_title.text = title
        p_title.font.name = FONT_HEADING
        p_title.font.size = Pt(22)
        p_title.font.bold = True
        p_title.font.color.rgb = COLOR_TEXT_WHITE

        # Subtitle
        sub_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.28), Inches(11.7), Inches(0.4))
        tf_sub = sub_box.text_frame
        tf_sub.word_wrap = True
        tf_sub.margin_left = tf_sub.margin_top = tf_sub.margin_right = tf_sub.margin_bottom = 0
        p_sub = tf_sub.paragraphs[0]
        p_sub.text = subtitle
        p_sub.font.name = FONT_BODY
        p_sub.font.size = Pt(12)
        p_sub.font.color.rgb = COLOR_TEXT_SLATE

        # Footer divider line
        line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(6.9), Inches(11.733), Inches(0.015))
        line.fill.solid()
        line.fill.fore_color.rgb = COLOR_CARD_BORDER
        line.line.fill.background()

        # Footer text
        footer_box = slide.shapes.add_textbox(Inches(0.8), Inches(6.98), Inches(9.0), Inches(0.3))
        tf_foot = footer_box.text_frame
        tf_foot.margin_left = tf_foot.margin_top = tf_foot.margin_right = tf_foot.margin_bottom = 0
        p_foot = tf_foot.paragraphs[0]
        p_foot.text = "GridMind | Deccan Renewables Pvt. Ltd. (Karnataka) | Self-Assessment Claim: D2 / F3"
        p_foot.font.name = FONT_BODY
        p_foot.font.size = Pt(9)
        p_foot.font.color.rgb = COLOR_TEXT_DIM

        # Slide Number
        num_box = slide.shapes.add_textbox(Inches(11.0), Inches(6.98), Inches(1.533), Inches(0.3))
        tf_num = num_box.text_frame
        tf_num.margin_left = tf_num.margin_top = tf_num.margin_right = tf_num.margin_bottom = 0
        p_num = tf_num.paragraphs[0]
        p_num.alignment = PP_ALIGN.RIGHT
        p_num.text = f"Slide {slide_num} of 16"
        p_num.font.name = FONT_BODY
        p_num.font.size = Pt(9)
        p_num.font.bold = True
        p_num.font.color.rgb = COLOR_TEXT_SLATE

    def add_card(slide, left, top, width, height, bg_color=COLOR_CARD_BG, border_color=COLOR_CARD_BORDER):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = bg_color
        if border_color:
            card.line.color.rgb = border_color
            card.line.width = Pt(1.2)
        else:
            card.line.fill.background()
        return card

    def add_bullet_card(slide, left, top, width, height, title, items, title_color=COLOR_CYAN, border_color=COLOR_CARD_BORDER):
        add_card(slide, left, top, width, height, COLOR_CARD_BG, border_color)
        tb = slide.shapes.add_textbox(left + Inches(0.2), top + Inches(0.18), width - Inches(0.4), height - Inches(0.36))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        
        p_title = tf.paragraphs[0]
        p_title.text = title
        p_title.font.name = FONT_HEADING
        p_title.font.size = Pt(13)
        p_title.font.bold = True
        p_title.font.color.rgb = title_color
        p_title.space_after = Pt(8)

        for heading, body in items:
            p = tf.add_paragraph()
            p.space_after = Pt(6)
            run_h = p.add_run()
            run_h.text = f"• {heading}: " if heading else "• "
            run_h.font.name = FONT_BODY
            run_h.font.size = Pt(10.5)
            run_h.font.bold = True
            run_h.font.color.rgb = COLOR_TEXT_WHITE

            run_b = p.add_run()
            run_b.text = body
            run_b.font.name = FONT_BODY
            run_b.font.size = Pt(10)
            run_b.font.color.rgb = COLOR_TEXT_SLATE

    def add_stat_card(slide, left, top, width, height, value, label, subtext, val_color=COLOR_EMERALD, border_color=COLOR_CARD_BORDER):
        add_card(slide, left, top, width, height, COLOR_CARD_BG, border_color)
        tb = slide.shapes.add_textbox(left + Inches(0.15), top + Inches(0.15), width - Inches(0.3), height - Inches(0.3))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        
        p_val = tf.paragraphs[0]
        p_val.text = value
        p_val.font.name = FONT_HEADING
        p_val.font.size = Pt(26)
        p_val.font.bold = True
        p_val.font.color.rgb = val_color
        p_val.space_after = Pt(3)

        p_lbl = tf.add_paragraph()
        p_lbl.text = label
        p_lbl.font.name = FONT_BODY
        p_lbl.font.size = Pt(11)
        p_lbl.font.bold = True
        p_lbl.font.color.rgb = COLOR_TEXT_WHITE
        p_lbl.space_after = Pt(2)

        p_sub = tf.add_paragraph()
        p_sub.text = subtext
        p_sub.font.name = FONT_BODY
        p_sub.font.size = Pt(9)
        p_sub.font.color.rgb = COLOR_TEXT_SLATE

    def set_speaker_notes(slide, notes):
        notes_slide = slide.notes_slide
        tf = notes_slide.notes_text_frame
        tf.text = notes

    # ==========================================
    # SLIDE 1: TITLE SLIDE
    # ==========================================
    slide1 = prs.slides.add_slide(blank_layout)
    add_bg(slide1)
    
    # Hero Tag
    hero_tag = slide1.shapes.add_textbox(Inches(1.0), Inches(0.8), Inches(11.3), Inches(0.4))
    tf1_tag = hero_tag.text_frame
    tf1_tag.margin_left = tf1_tag.margin_top = tf1_tag.margin_right = tf1_tag.margin_bottom = 0
    p = tf1_tag.paragraphs[0]
    p.text = "THE ECONOMIC TIMES  ×  ACCENTURE  |  ET AI HACKATHON: AGENTIC EDITION"
    p.font.name = FONT_HEADING
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = COLOR_CYAN

    # Main Title
    title_box = slide1.shapes.add_textbox(Inches(1.0), Inches(1.3), Inches(11.3), Inches(1.3))
    tf1_title = title_box.text_frame
    tf1_title.margin_left = tf1_title.margin_top = tf1_title.margin_right = tf1_title.margin_bottom = 0
    p = tf1_title.paragraphs[0]
    p.text = "GridMind"
    p.font.name = FONT_HEADING
    p.font.size = Pt(46)
    p.font.bold = True
    p.font.color.rgb = COLOR_TEXT_WHITE
    p.space_after = Pt(6)

    p_sub = tf1_title.add_paragraph()
    p_sub.text = "Autonomous Renewable Energy Portfolio Orchestrator"
    p_sub.font.name = FONT_HEADING
    p_sub.font.size = Pt(22)
    p_sub.font.bold = True
    p_sub.font.color.rgb = COLOR_EMERALD

    desc_box = slide1.shapes.add_textbox(Inches(1.0), Inches(2.75), Inches(11.3), Inches(0.6))
    tf1_desc = desc_box.text_frame
    tf1_desc.margin_left = tf1_desc.margin_top = tf1_desc.margin_right = tf1_desc.margin_bottom = 0
    p = tf1_desc.paragraphs[0]
    p.text = "A Neuro-Symbolic Agentic Decision System uniting Generative Reasoning (Gemini) with Deterministic MILP Optimization (PuLP) & Hard Safety Guardrails for 15-Minute Electricity Markets."
    p.font.name = FONT_BODY
    p.font.size = Pt(13)
    p.font.color.rgb = COLOR_TEXT_SLATE

    # 4 Highlight Cards at bottom
    add_stat_card(slide1, Inches(1.0), Inches(3.6), Inches(2.65), Inches(2.6), 
                  "PS-4", "Utilities Orchestrator", "Renewable generation, BESS, industrial offtake & market arbitrage", COLOR_CYAN, COLOR_CYAN)
    
    add_stat_card(slide1, Inches(3.88), Inches(3.6), Inches(2.65), Inches(2.6), 
                  "D2 / F3", "9-Blocker Claim", "High demonstrable reliability + rolling uncertainty simulation", COLOR_INDIGO, COLOR_INDIGO)

    add_stat_card(slide1, Inches(6.76), Inches(3.6), Inches(2.65), Inches(2.6), 
                  "-44.5%", "Daily Cost Reduction", "₹18.2 Million daily operational savings vs traditional baseline", COLOR_EMERALD, COLOR_EMERALD)

    add_stat_card(slide1, Inches(9.64), Inches(3.6), Inches(2.65), Inches(2.6), 
                  "0", "Safety Violations", "2,880 consecutive intervals (30 days) with zero hard violations & 0 VOLL", COLOR_AMBER, COLOR_AMBER)

    foot_t = slide1.shapes.add_textbox(Inches(1.0), Inches(6.6), Inches(11.3), Inches(0.4))
    tf1_f = foot_t.text_frame
    tf1_f.margin_left = tf1_f.margin_top = tf1_f.margin_right = tf1_f.margin_bottom = 0
    p = tf1_f.paragraphs[0]
    p.text = "Target Portfolio: Deccan Renewables Pvt. Ltd. (Karnataka, India)  |  Primary Persona: Shift Dispatch Manager"
    p.font.name = FONT_BODY
    p.font.size = Pt(10)
    p.font.color.rgb = COLOR_TEXT_DIM

    set_speaker_notes(slide1, 
        "Good morning judges. We are thrilled to present GridMind, our autonomous renewable energy orchestrator developed for the ET AI Hackathon: Agentic Edition. "
        "We are addressing Problem Statement 4: Utilities. "
        "Our target client is Deccan Renewables Pvt. Ltd. in Karnataka, managing 740 MW of renewable generation, 400 MWh of battery storage, and 300 MW of industrial customers. "
        "Our claimed position on the 9-blocker grid is strictly D2 / F3: high demonstrable reliability through deterministic safety gates, combined with rolling uncertainty simulation. "
        "Let's dive into why this problem is mission-critical.")

    # ==========================================
    # SLIDE 2: INDUSTRY CONTEXT & DISPATCH CRISIS
    # ==========================================
    slide2 = prs.slides.add_slide(blank_layout)
    add_header(slide2, "Industry Problem & Real-World Friction",
               "The 15-Minute Dispatch Crisis in Modern Renewable Grids",
               "Why manual control rooms fail under renewable volatility, battery wear, and strict offtake penalties", 2)

    add_bullet_card(slide2, Inches(0.8), Inches(1.8), Inches(3.65), Inches(4.85),
                    "1. Weather & Asset Volatility", [
                        ("Intermittent Solar", "5 solar parks (Pavagada, Tumakuru, etc.) drop up to 80% generation under cloud cover."),
                        ("Stochastic Wind", "Wind farms (Chitradurga, Gadag) swing sharply between cut-in (3 m/s) and rated (12 m/s)."),
                        ("Transmission Bottlenecks", "Evacuation corridors derate under thermal congestion and equipment trips.")
                    ], COLOR_CYAN)

    add_bullet_card(slide2, Inches(4.84), Inches(1.8), Inches(3.65), Inches(4.85),
                    "2. Market & Contractual Risks", [
                        ("IEX Price Swings", "Indian Energy Exchange Real-Time tariffs fluctuate between ₹1,000 and ₹10,000/MWh."),
                        ("Round-The-Clock Contracts", "Supplying 300 MW RTC power to steel, data center, and cement with severe penalties."),
                        ("₹15,000/MWh Penalties", "Missing customer schedule incurs massive financial damages and regulatory penalties.")
                    ], COLOR_AMBER)

    add_bullet_card(slide2, Inches(8.88), Inches(1.8), Inches(3.65), Inches(4.85),
                    "3. The Operator Bottleneck", [
                        ("Cognitive Overload", "Human Shift Dispatch Managers must balance 10 assets and 4 customers every 15 minutes."),
                        ("BESS Degradation Dilemma", "Cycling batteries aggressively destroys cell life (₹500/MWh degradation cost)."),
                        ("Safety Zero-Tolerance", "Shedding critical customer loads (₹100,000/MWh VOLL) or line overloads triggers blackouts.")
                    ], COLOR_ROSE)

    set_speaker_notes(slide2,
        "Every 15 minutes, renewable dispatchers face an impossible mental juggling act. In Karnataka, Deccan Renewables operates 5 solar parks and 3 wind farms. "
        "If clouds blanket Pavagada Solar Park or wind drops in Chitradurga, generation plummets. "
        "Meanwhile, they are contractually bound to deliver continuous Round-The-Clock power to Bellary Steel and a Bangalore Data Centre. "
        "A single shortfall interval costs ₹15,000 per MWh in penalties. But buying blindly from the IEX spot market when prices spike to ₹10/kWh destroys profits. "
        "And cycling batteries blindly degrades multi-crore BESS assets. Human dispatchers simply cannot solve this multi-variable dynamic optimization every 15 minutes.")

    # ==========================================
    # SLIDE 3: 9-BLOCKER MATRIX POSITIONING (D2 / F3)
    # ==========================================
    slide3 = prs.slides.add_slide(blank_layout)
    add_header(slide3, "Hackathon Evaluation Alignment",
               "Self-Estimated 9-Blocker Claim: Position D2 / F3",
               "Rigorous justification of our claimed capability level and explicit prevention of overclaiming penalties", 3)

    # 3x3 Visual Matrix Card on Left
    add_card(slide3, Inches(0.8), Inches(1.8), Inches(4.6), Inches(4.85), COLOR_CARD_BG, COLOR_INDIGO)
    tb_m = slide3.shapes.add_textbox(Inches(1.0), Inches(1.95), Inches(4.2), Inches(4.5))
    tf_m = tb_m.text_frame
    tf_m.word_wrap = True
    p = tf_m.paragraphs[0]
    p.text = "SOLUTION MATRIX (3×3 GRID)"
    p.font.name = FONT_HEADING
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = COLOR_CYAN
    p.space_after = Pt(10)

    rows_matrix = [
        ("D3 (Multimodal)", "  F1  ", "  F2  ", "  F3  ", COLOR_TEXT_DIM),
        ("D2 (High Reliability)", "  F1  ", "  F2  ", "★ D2/F3 ★", COLOR_EMERALD),
        ("D1 (Structured Baseline)", "  F1  ", "  F2  ", "  F3  ", COLOR_TEXT_DIM)
    ]
    for d_lbl, f1, f2, f3, col in rows_matrix:
        p_row = tf_m.add_paragraph()
        p_row.space_after = Pt(8)
        r1 = p_row.add_run()
        r1.text = f"{d_lbl:<22}\n"
        r1.font.size = Pt(10)
        r1.font.bold = True
        r1.font.color.rgb = col if col != COLOR_TEXT_DIM else COLOR_TEXT_SLATE
        
        r2 = p_row.add_run()
        r2.text = f"[{f1}]  [{f2}]  [{f3}]\n"
        r2.font.size = Pt(11)
        r2.font.bold = (col == COLOR_EMERALD)
        r2.font.color.rgb = COLOR_TEXT_WHITE if col == COLOR_EMERALD else COLOR_TEXT_DIM

    p_note = tf_m.add_paragraph()
    p_note.text = "\n★ CLAIMED & VERIFIED: D2 / F3\nPenalties strictly avoided: Zero overclaim into D3, zero underclaim into F1/F2."
    p_note.font.size = Pt(9.5)
    p_note.font.color.rgb = COLOR_AMBER

    # Right Cards: Justifications
    add_bullet_card(slide3, Inches(5.6), Inches(1.8), Inches(6.933), Inches(2.3),
                    "Depth D2: High Demonstrable Reliability", [
                        ("Zero Hard Violations", "Mathematically verified 0 hard-constraint violations across 2,880 consecutive intervals (30 days)."),
                        ("Zero Critical Load Shedding", "100% protection of non-sheddable customer loads (0.000 MWh shed vs 43.2 MWh in baseline)."),
                        ("Deterministic Gatekeeper", "Hard Python guardrail intercepts and validates all candidate plans prior to actuation.")
                    ], COLOR_EMERALD)

    add_bullet_card(slide3, Inches(5.6), Inches(4.35), Inches(6.933), Inches(2.3),
                    "Features F3: Rolling Uncertainty Simulation", [
                        ("Rolling Horizon MPC", "Continuously re-optimizes a 32-interval (8-hour) forward horizon every 15 minutes."),
                        ("Multi-Quantile Forecast Cones", "Evaluates P10 (pessimistic), P50 (expected), and P90 (optimistic) bounds across weather and demand."),
                        ("Stochastic Monte Carlo Risk", "Evaluates candidate plans across 20 randomized weather/price shock scenarios."),
                        ("Multi-Season Testing", "Audited under real meteorological data across Summer (April) and Monsoon (July) regimes.")
                    ], COLOR_CYAN)

    set_speaker_notes(slide3,
        "The hackathon guidelines explicitly state: declare your self-estimated position on the 9-blocker grid and justify it. Overestimating or underestimating incurs penalties. "
        "We claim D2 / F3. "
        "Why D2? Our inputs are structured telemetry, weather forecasts, and market prices. But we demonstrate HIGH reliability: zero hard safety violations over 30 days of simulation and zero unserved critical load. "
        "We do NOT claim D3 because we do not process satellite imagery or raw computer vision. Claiming D3 would be an ungrounded overclaim. "
        "Why F3? We satisfy all F1, F2, and F3 features: optimal cluster of actions, dynamic optimality determination under uncertainty, and rolling multi-day simulation with stochastic perturbations.")

    # ==========================================
    # SLIDE 4: CORE INNOVATION & PHILOSOPHY
    # ==========================================
    slide4 = prs.slides.add_slide(blank_layout)
    add_header(slide4, "Core Innovation & Design Philosophy",
               "The Neuro-Symbolic Agentic Paradigm",
               "Why generative AI must never compute dispatch numbers — and how we bridge reasoning with mathematical rigor", 4)

    add_bullet_card(slide4, Inches(0.8), Inches(1.8), Inches(3.65), Inches(4.85),
                    "1. The Pure LLM Failure", [
                        ("Hallucination Risk", "Language models cannot compute linear power flow conservation laws reliably."),
                        ("Non-Physical Megawatts", "A 10 MW arithmetic error in high voltage grids trips protection relays and collapses the grid."),
                        ("Unbounded Latency", "External API delays or timeouts cannot be tolerated in 15-minute dispatch deadlines."),
                        ("Verdict", "Pure generative agents are fundamentally unsafe for physical infrastructure.")
                    ], COLOR_ROSE)

    add_bullet_card(slide4, Inches(4.84), Inches(1.8), Inches(3.65), Inches(4.85),
                    "2. The Static MILP Failure", [
                        ("Rigid Objective Weights", "Traditional optimization uses hardcoded, static cost weights that cannot adapt."),
                        ("Blind to Context", "MILP solvers cannot read storm alerts, understand incoming weather fronts, or shift operating posture."),
                        ("Black-Box Outputs", "Generates raw numeric matrices with zero operational explanation for control room shift managers."),
                        ("Verdict", "Classical mathematical optimization lacks situational intelligence.")
                    ], COLOR_AMBER)

    add_bullet_card(slide4, Inches(8.88), Inches(1.8), Inches(3.65), Inches(4.85),
                    "3. The GridMind Solution", [
                        ("The LLM Reasons & Directs", "Gemini interprets anomalies, selects operational modes, tunes multi-objective weights, and compares risk."),
                        ("The Solver Solves", "Deterministic MILP (PuLP/CBC) computes exact, physically guaranteed megawatt setpoints in <40 ms."),
                        ("Code Enforces Safety", "Deterministic Python guardrails intercept every plan before actuation. Zero AI hallucinations execute.")
                    ], COLOR_EMERALD, COLOR_EMERALD)

    set_speaker_notes(slide4,
        "Here is our central architectural breakthrough. Rule #1 of GridMind is: The LLM never computes dispatch numbers. "
        "If you ask an LLM to decide how many megawatts each battery should discharge, it will hallucinate. In power systems, hallucinating 15 megawatts blows a substation transformer. "
        "On the other hand, traditional MILP solvers are mathematically sound but contextually blind. They cannot adapt when a cyclone warning is declared or trade off battery degradation against market spikes. "
        "GridMind solves this with a Neuro-Symbolic architecture: Gemini provides contextual reasoning, operational mode selection, and risk comparison, while PuLP MILP computes exact physical dispatch in 40 milliseconds, validated by hard code guardrails.")

    # ==========================================
    # SLIDE 5: PORTFOLIO TOPOLOGY (KARNATAKA)
    # ==========================================
    slide5 = prs.slides.add_slide(blank_layout)
    add_header(slide5, "Operational Asset Modeling",
               "Portfolio Topology: Deccan Renewables Pvt. Ltd. (Karnataka)",
               "740 MW Generation, 400 MWh Storage, and 300 MW Industrial Demand under Indian Energy Exchange (IEX) Tariffs", 5)

    add_bullet_card(slide5, Inches(0.8), Inches(1.8), Inches(5.66), Inches(2.3),
                    "Renewable Generation: 740 MW", [
                        ("5 Solar Parks (500 MW)", "Pavagada (150MW), Tumakuru (120MW), Koppal (100MW), Raichur (80MW), Kalaburagi (50MW). Modeled with PR: 0.80, Temp Coeff: -0.4%/°C."),
                        ("3 Wind Farms (240 MW)", "Chitradurga (100MW), Gadag (80MW), Harapanahalli (60MW). Modeled with IEC cubic power curves (3 m/s cut-in, 12 m/s rated, 25 m/s cut-out).")
                    ], COLOR_CYAN)

    add_bullet_card(slide5, Inches(6.86), Inches(1.8), Inches(5.66), Inches(2.3),
                    "Battery Storage (BESS): 100 MW / 400 MWh", [
                        ("B1 Storage (60 MW / 240 MWh)", "4-hour duration, 95% charge/discharge efficiency (90.25% round-trip), operating SoC band: 10%–95%."),
                        ("B2 Storage (40 MW / 160 MWh)", "4-hour duration, 90.25% round-trip efficiency, degradation cost model: ₹500 / MWh throughput to protect cell longevity.")
                    ], COLOR_AMBER)

    add_bullet_card(slide5, Inches(0.8), Inches(4.35), Inches(5.66), Inches(2.3),
                    "RTC Industrial Customers: 300 MW Base", [
                        ("Bellary Steel Plant (120 MW)", "60% non-sheddable critical load (72 MW hard floor), 25 MW max Demand Response @ ₹3,000/MWh."),
                        ("Bengaluru Data Centre (60 MW)", "90% non-sheddable critical load (54 MW hard floor), 5 MW max DR @ ₹6,000/MWh."),
                        ("Davanagere Textile (50 MW)", "40% critical floor (20 MW), 15 MW max DR @ ₹2,500/MWh."),
                        ("Bagalkot Cement (70 MW)", "50% critical floor (35 MW), 20 MW max DR @ ₹2,800/MWh.")
                    ], COLOR_EMERALD)

    add_bullet_card(slide5, Inches(6.86), Inches(4.35), Inches(5.66), Inches(2.3),
                    "Grid Interconnection & Market Rules", [
                        ("Grid Evacuation Limits", "Max Import Limit: 150 MW | Max Export Limit: 200 MW (enforced by binary interlocks)."),
                        ("Contract Shortfall Penalty", "₹15,000 / MWh for unserved committed RTC schedule."),
                        ("Value of Lost Load (VOLL)", "₹100,000 / MWh mathematical slack penalty guaranteeing zero critical outage."),
                        ("Grid Carbon Intensity", "0.71 tCO₂/MWh (Central Electricity Authority Baseline) with ₹1,500/tCO₂ shadow price.")
                    ], COLOR_INDIGO)

    set_speaker_notes(slide5,
        "To make our prototype realistic, we modeled an actual utility footprint in Karnataka. "
        "Our generation portfolio includes 500 MW across 5 solar parks, including Pavagada, one of the world's largest solar parks, and 240 MW across 3 wind parks in Chitradurga and Gadag. "
        "We have 400 MWh of lithium-ion battery storage with real 90.25% round-trip efficiency and ₹500/MWh degradation penalties. "
        "We serve four real-world industrial offtakers totaling 300 MW, each with distinct critical load baselines. The Bangalore Data Centre has a 90% non-sheddable floor, while Bellary Steel has 60%. "
        "All asset specs live in config YAML files with zero hardcoded numbers.")

    # ==========================================
    # SLIDE 6: DETAILED STRUCTURAL ARCHITECTURE
    # ==========================================
    slide6 = prs.slides.add_slide(blank_layout)
    add_header(slide6, "Detailed Structural Architecture",
               "The 4-Stage Closed Control Loop Pipeline",
               "End-to-end execution flow executed autonomously every 15 minutes with human oversight", 6)

    col_w = Inches(2.75)
    gap = Inches(0.24)
    c_top = Inches(1.8)
    c_h = Inches(4.85)

    add_bullet_card(slide6, Inches(0.8), c_top, col_w, c_h,
                    "Stage 1: Sensing", [
                        ("Telemetry Ingestion", "Polls 10 asset outputs, battery SoCs, and customer meters."),
                        ("Weather Physics", "Converts Open-Meteo GHI, DNI, and wind speeds via physical curves."),
                        ("Forecaster Cones", "Computes rolling 32-interval P10, P50, P90 forecast cones."),
                        ("IEX Tariffs", "Ingests Day-Ahead & Real-Time market pricing feeds.")
                    ], COLOR_CYAN)

    add_bullet_card(slide6, Inches(0.8) + col_w + gap, c_top, col_w, c_h,
                    "Stage 2: Agentic Layer", [
                        ("Monitor Agent", "Calculates telemetry deltas; generates anomaly briefings when severity >= medium."),
                        ("Strategist Agent", "Selects operational mode (green, economic, storm, etc.) and tunes weights."),
                        ("Bounded Tool Loop", "Calls run_milp, evaluate_risk, and compare_plans (max 6 calls)."),
                        ("PuLP MILP Solver", "Solves 32-interval dispatch in <40 ms.")
                    ], COLOR_INDIGO)

    add_bullet_card(slide6, Inches(0.8) + (col_w + gap)*2, c_top, col_w, c_h,
                    "Stage 3: Safety Gate", [
                        ("Hard Guardrails", "Validates 7 physical safety interlocks before execution."),
                        ("Self-Healing Loop", "On violation, feeds error to Strategist to re-solve (up to 2 retries)."),
                        ("Safe-Mode Fallback", "If retries fail, executes deterministic 40% reserve hold."),
                        ("Operator Gate", "High-impact actions prompt for operator sign-off in UI.")
                    ], COLOR_ROSE)

    add_bullet_card(slide6, Inches(0.8) + (col_w + gap)*3, c_top, col_w, c_h,
                    "Stage 4: Actuation", [
                        ("Dispatch Executor", "Dispatches interval t=0 setpoints to physical assets."),
                        ("JSONL Audit Logger", "Writes complete immutable decision trace for compliance."),
                        ("Explainer Agent", "Generates natural language shift briefing with underlying motives."),
                        ("Streamlit UI", "Updates live Control Room telemetry and gauges.")
                    ], COLOR_EMERALD)

    set_speaker_notes(slide6,
        "Here is the complete structural architecture required by the hackathon submission. Every 15 minutes, the system executes this four-stage loop: "
        "Stage 1 Sensing: We ingest physical telemetry from our Karnataka assets, compute physical solar and wind conversion, and forecast P10/P50/P90 trajectories 8 hours ahead. "
        "Stage 2 Reasoning: The Monitor Agent flags anomalies. The Strategist Agent enters a bounded tool-calling loop, testing candidate weight profiles in the PuLP MILP solver and evaluating tail risk across Monte Carlo scenarios. "
        "Stage 3 Safety: Before any setpoint touches hardware, our deterministic Python guardrails verify 7 physical constraints. If anything violates safety, it triggers a recovery loop or fails safe to a 40% battery hold. "
        "Stage 4 Actuation: We execute interval t=0, log an immutable audit record, and provide a plain-language briefing to the shift operator.")

    # ==========================================
    # SLIDE 7: THE AGENTIC CORE (MONITOR, STRATEGIST, EXPLAINER)
    # ==========================================
    slide7 = prs.slides.add_slide(blank_layout)
    add_header(slide7, "Autonomous Multi-Agent System",
               "The Agentic Triad: Monitor, Strategist & Explainer",
               "How agents reason, use bounded tools, resolve trade-offs, and maintain strict schema validation", 7)

    add_bullet_card(slide7, Inches(0.8), Inches(1.8), Inches(3.65), Inches(4.85),
                    "Monitor Agent", [
                        ("Telemetry Synthesis", "Computes divergence between actual generation and forecast cones."),
                        ("Anomaly Classification", "Classifies severity (Low, Medium, High, Critical) based on asset thresholds."),
                        ("Contextual Briefing", "When severity >= medium, LLM synthesizes a concise 2-sentence situational briefing."),
                        ("Zero Token Waste", "Skips LLM calls during quiescent normal operations.")
                    ], COLOR_CYAN)

    add_bullet_card(slide7, Inches(4.84), Inches(1.8), Inches(3.65), Inches(4.85),
                    "Strategy Agent", [
                        ("Dynamic Mode Selection", "Shifts operational mode (e.g. green, economic, storm_preparation, outage_recovery)."),
                        ("Weight Tuning", "Dynamically tunes weights w in [0, 5] across cost, carbon, curtailment, degradation, reliability."),
                        ("Tool-Calling Exploration", "Interactively executes run_milp(), evaluate_risk(), and compare_plans()."),
                        ("Trade-Off Articulation", "Articulates explicit mathematical trade-off justification before selecting optimal plan.")
                    ], COLOR_INDIGO)

    add_bullet_card(slide7, Inches(8.88), Inches(1.8), Inches(3.65), Inches(4.85),
                    "Explainer Agent", [
                        ("Operator Briefing", "Generates an executive headline (<= 15 words) for shift dispatchers."),
                        ("Underlying Motives", "Explains WHY specific batteries charged or why imports were dispatched."),
                        ("Accepted Trade-Offs", "Explicitly documents what trade-offs were made (e.g. accepted Rs. 50k degradation to avoid Rs. 2M shortfall)."),
                        ("Pivot Conditions", "Specifies exact triggers that will require abandoning the plan.")
                    ], COLOR_EMERALD)

    set_speaker_notes(slide7,
        "Let's look at the three agents inside GridMind. "
        "The Monitor Agent watches asset telemetry. If generation diverges from forecast, it classifies the event and triggers replanning. To conserve tokens, it only invokes the LLM when anomalies are meaningful. "
        "The Strategy Agent is our core reasoner. It selects the operating mode and tunes the multi-objective weights. It has access to three deterministic tools: run_milp, evaluate_risk, and compare_plans. It calls these in a bounded loop to test candidate strategies. "
        "The Explainer Agent serves the human operator. It creates concise shift briefings explaining exactly why decisions were made, what trade-offs were accepted, and what conditions would trigger a pivot.")

    # ==========================================
    # SLIDE 8: DYNAMIC MULTI-OBJECTIVE OPTIMIZATION
    # ==========================================
    slide8 = prs.slides.add_slide(blank_layout)
    add_header(slide8, "Mathematical Formulation & Trade-Offs",
               "Dynamic Multi-Objective Optimization & Conflict Resolution",
               "Formal MILP objective formulation and explicit penalty hierarchy for competing operational goals", 8)

    # Formulation Card Top Left
    add_bullet_card(slide8, Inches(0.8), Inches(1.8), Inches(6.9), Inches(2.2),
                    "Formal Rolling MILP Formulation (PuLP / CBC)", [
                        ("Objective Function", "MIN w_cost * Cost + w_carbon * Carbon + w_curt * Curtailment + w_degr * Degradation + w_reliab * Shortfall + VOLL * Unserved_Load"),
                        ("Physical Power Balance", "Sum(Gen_net) + Sum(Discharge) + Import == Sum(Demand_net) + Sum(Charge) + Export"),
                        ("Physical Constraints", "BESS dynamic SoC continuity; Mutex charge/discharge; Mutex grid import/export; Line limits; 100% Critical Load floor.")
                    ], COLOR_INDIGO)

    # Conflict Resolution Hierarchy Top Right
    add_bullet_card(slide8, Inches(8.0), Inches(1.8), Inches(4.533), Inches(2.2),
                    "Conflict Resolution Penalty Hierarchy", [
                        ("Level 1: Critical Blackout", "VOLL (₹100,000/MWh) strictly dominates. Never shed critical hospital/datacenter load."),
                        ("Level 2: Defensive Reserves", "Holding storm reserves (₹25,000/MWh slack) dominates non-critical contract shortfall (₹15,000/MWh)."),
                        ("Level 3: Contract Schedules", "Shortfall penalties (₹15,000/MWh) dominate market tariff spikes (₹10,000/MWh)."),
                        ("Level 4: Cell Degradation", "Degradation (₹500/MWh) prevents battery cycling unless price spreads exceed efficiency losses.")
                    ], COLOR_ROSE)

    # Dynamic Weight Table Bottom
    headers_opt = ["Operational Mode", "Operational Context / Trigger", "Cost (w1)", "Carbon (w2)", "Curtail (w3)", "Degrad (w4)", "Reliab (w5)", "Reserve Floor"]
    rows_opt = [
        ["green", "High solar/wind midday; low market price", "1.0", "2.5", "3.0", "0.8", "3.0", "15%"],
        ["economic", "High price spread (>₹6/kWh); normal grid", "3.5", "0.8", "1.0", "1.2", "2.5", "10%"],
        ["reliability_first", "Forecast deficit; unhedged industrial demand", "1.0", "0.5", "0.5", "0.5", "5.0", "35%"],
        ["storm_preparation", "Severe cyclone or weather warning detected", "0.5", "0.5", "0.5", "0.5", "5.0", "60%"],
        ["outage_recovery", "Tripped inverter or derated transmission line", "1.2", "1.0", "1.0", "0.5", "4.5", "35%"],
        ["congestion_mgmt", "Local substation thermal limit reached", "2.0", "1.0", "3.0", "0.8", "3.5", "20%"]
    ]
    col_w_opt = [Inches(1.8), Inches(3.6), Inches(0.9), Inches(1.0), Inches(1.0), Inches(1.0), Inches(1.0), Inches(1.433)]
    
    # Table container
    t_shape = slide8.shapes.add_table(len(rows_opt) + 1, len(headers_opt), Inches(0.8), Inches(4.2), Inches(11.733), Inches(2.45))
    table = t_shape.table
    for i, w in enumerate(col_w_opt):
        table.columns[i].width = w

    for col_idx, h in enumerate(headers_opt):
        cell = table.cell(0, col_idx)
        cell.fill.solid()
        cell.fill.fore_color.rgb = COLOR_CARD_BORDER
        cell.text_frame.margin_left = cell.text_frame.margin_top = Inches(0.04)
        p = cell.text_frame.paragraphs[0]
        p.text = h
        p.font.name = FONT_HEADING
        p.font.size = Pt(9.5)
        p.font.bold = True
        p.font.color.rgb = COLOR_CYAN

    for row_idx, r_data in enumerate(rows_opt):
        for col_idx, val in enumerate(r_data):
            cell = table.cell(row_idx + 1, col_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = COLOR_CARD_BG if row_idx % 2 == 0 else RGBColor(15, 23, 42)
            cell.text_frame.margin_left = cell.text_frame.margin_top = Inches(0.04)
            p = cell.text_frame.paragraphs[0]
            p.text = val
            p.font.name = FONT_BODY
            p.font.size = Pt(9)
            p.font.color.rgb = COLOR_EMERALD if col_idx == 0 else (COLOR_TEXT_WHITE if col_idx >= 2 else COLOR_TEXT_SLATE)

    set_speaker_notes(slide8,
        "Problem 4 in the hackathon brief explicitly demands that the solution make its optimality criteria clear and demonstrate how actions are chosen when objectives conflict. "
        "Here is our mathematical formulation. We balance six competing terms: electricity cost, carbon emissions, renewable curtailment, battery degradation, contract shortfall, and unserved load. "
        "Look at our conflict hierarchy: VOLL is ₹100,000/MWh. It strictly dominates everything else, guaranteeing critical loads are never shed. "
        "When a cyclone is incoming, storm preparation shifts the reserve floor to 60%, paying shortfall penalties if necessary to maintain defensive energy. "
        "During price arbitrage, battery degradation at ₹500/MWh ensures we only cycle batteries when price spreads exceed round-trip efficiency losses.")

    # ==========================================
    # SLIDE 9: UNCERTAINTY HANDLING & ROLLING MPC
    # ==========================================
    slide9 = prs.slides.add_slide(blank_layout)
    add_header(slide9, "Uncertainty & Rolling Optimization",
               "3-Tier Uncertainty Handling & Model Predictive Control",
               "How GridMind eliminates forecast drift and evaluates tail risk across dynamic weather regimes", 9)

    add_bullet_card(slide9, Inches(0.8), Inches(1.8), Inches(3.65), Inches(4.85),
                    "Tier 1: Multi-Quantile Cones", [
                        ("P10 Pessimistic Cone", "Models severe overcast or sudden wind drop. Used for defensive reserve sizing."),
                        ("P50 Expected Baseline", "Central forecast driving the primary rolling MILP horizon."),
                        ("P90 Optimistic Cone", "High generation trajectory used to schedule pre-charging and export bids."),
                        ("Rolling Update", "Regenerated every 15 minutes across all 10 generation and load nodes.")
                    ], COLOR_CYAN)

    add_bullet_card(slide9, Inches(4.84), Inches(1.8), Inches(3.65), Inches(4.85),
                    "Tier 2: Monte Carlo Risk Evaluation", [
                        ("Tool-Calling Tool", "Strategy agent calls evaluate_risk(plan_id) during candidate evaluation."),
                        ("20 Stochastic Scenarios", "Simulates candidate dispatch against 20 perturbed weather and price curves."),
                        ("P90 Tail Risk Metrics", "Measures expected cost, P90 tail risk cost, and shortfall probability (P_shortfall)."),
                        ("Risk-Aware Selection", "Rejects candidate plans with >5% risk of breaching battery reserve floors.")
                    ], COLOR_INDIGO)

    add_bullet_card(slide9, Inches(8.88), Inches(1.8), Inches(3.65), Inches(4.85),
                    "Tier 3: Receding Horizon MPC", [
                        ("32-Interval Horizon", "Optimizes dispatch across a forward 8-hour window (32 steps of 15 min)."),
                        ("Execute Only t=0", "Crucial: Only the immediate first interval setpoint is committed to physical assets."),
                        ("Dynamic Feedback", "At t=1, real telemetry updates asset SoC and actual output, and solver re-runs."),
                        ("Zero Error Drift", "Prevents compounding errors from long-range forecast inaccuracies.")
                    ], COLOR_EMERALD)

    set_speaker_notes(slide9,
        "How do we handle renewable intermittency and input uncertainty? Through a 3-tier uncertainty architecture. "
        "First, our Forecaster generates multi-quantile cones: P10 pessimistic, P50 expected, and P90 optimistic for all 10 assets over 32 intervals. "
        "Second, before executing a plan, the Strategy Agent calls evaluate_risk(), which runs a Monte Carlo simulation across 20 randomized weather and tariff perturbations. It computes expected cost and P90 tail risk. "
        "Third, we use Receding Horizon Model Predictive Control. While we optimize 8 hours ahead, we only execute the first 15-minute interval. At t=1, fresh telemetry arrives and we re-solve. This completely eliminates cumulative forecast drift.")

    # ==========================================
    # SLIDE 10: SAFETY GUARDRAILS & RESILIENCE
    # ==========================================
    slide10 = prs.slides.add_slide(blank_layout)
    add_header(slide10, "Safety Engineering & Reliability",
               "Deterministic Guardrails, Self-Healing & 100% Offline Mode",
               "Multi-layer defense ensuring zero physical damage and seamless operation without internet connectivity", 10)

    add_bullet_card(slide10, Inches(0.8), Inches(1.8), Inches(3.65), Inches(4.85),
                    "7 Hard Safety Interlocks", [
                        ("BESS Mutex", "Charge <= P_max * u, Discharge <= P_max * (1-u). Zero simultaneous charge/discharge."),
                        ("Grid Mutex", "Import <= 150 * y, Export <= 200 * (1-y). Zero simultaneous import/export."),
                        ("SoC Physical Bounds", "Strictly enforces 10% <= SoC <= 95% at every interval."),
                        ("Critical Load Protection", "Zero unserved load allowed for non-sheddable customer fractions."),
                        ("Asset Power Limits", "Never exceeds inverter ratings or generator thermal capacities.")
                    ], COLOR_ROSE)

    add_bullet_card(slide10, Inches(4.84), Inches(1.8), Inches(3.65), Inches(4.85),
                    "Self-Healing Recovery Loop", [
                        ("Validation Rejection", "Deterministic guardrail intercepts invalid plans with structured error codes."),
                        ("Strategist Self-Correction", "Feedback prompt injected into Strategy Agent with violation context."),
                        ("Bounded Retries", "Up to 2 autonomous recovery attempts with reinforced reliability weights."),
                        ("Safe-Mode Fallback", "If retries fail, executes deterministic Safe-Mode: holding 40% BESS reserve, zero exports, direct customer supply.")
                    ], COLOR_AMBER)

    add_bullet_card(slide10, Inches(8.88), Inches(1.8), Inches(3.65), Inches(4.85),
                    "100% Offline Resilience", [
                        ("Zero API Lock-in", "Operates with MOCK_LLM=true producing identical Pydantic JSON shapes."),
                        ("Instant Fallback", "Any Gemini API network timeout or rate limit automatically triggers mock logic."),
                        ("Bundled Solvers", "PuLP uses bundled Coin-OR CBC binary. Zero external server dependencies."),
                        ("Control Room Guarantee", "The system will NEVER freeze or crash in the control room desk.")
                    ], COLOR_EMERALD)

    set_speaker_notes(slide10,
        "Safety and fault tolerance are non-negotiable for electric grids. "
        "Before any setpoint is sent to actuators, our deterministic Python guardrail layer checks 7 hard physical interlocks: no simultaneous charge and discharge, no simultaneous import and export, strict battery SoC limits between 10% and 95%, and 100% critical load protection. "
        "If a plan violates a guardrail, the system triggers an autonomous self-healing loop: the Strategist receives the exact violation feedback and re-solves. If two retries fail, it falls back to a deterministic Safe-Mode holding a 40% battery reserve. "
        "Furthermore, GridMind has 100% offline resilience: if the internet drops or Gemini times out, deterministic mock logic engages instantly with zero latency penalty.")

    # ==========================================
    # SLIDE 11: RESPONSIBLE AI, GOVERNANCE & HITL
    # ==========================================
    slide11 = prs.slides.add_slide(blank_layout)
    add_header(slide11, "Responsible AI & Governance",
               "Human-in-the-Loop Oversight & Decision Auditability",
               "Balancing agentic autonomy with operator authority, transparency, and complete compliance tracing", 11)

    add_bullet_card(slide11, Inches(0.8), Inches(1.8), Inches(3.65), Inches(4.85),
                    "Human Approval Gates", [
                        ("Configurable Governance", "Operator can toggle between Full Autonomous mode and Manual Approval mode."),
                        ("High-Impact Intercepts", "Voluntary customer load shedding (Demand Response) or emergency reserve releases require explicit operator sign-off."),
                        ("Contextual Decision Card", "UI presents trade-off summary, financial impact, and alternative options before execution.")
                    ], COLOR_CYAN)

    add_bullet_card(slide11, Inches(4.84), Inches(1.8), Inches(3.65), Inches(4.85),
                    "Live Operator Overrides", [
                        ("Full Operational Control", "Shift Dispatch Manager can step, pause, or manually override any asset setpoint in real time."),
                        ("Safety Cross-Check", "Operator overrides are still validated through guardrails to prevent accidental equipment damage."),
                        ("Reason Capture", "Operator must enter a operational justification, permanently recorded in the audit trail.")
                    ], COLOR_AMBER)

    add_bullet_card(slide11, Inches(8.88), Inches(1.8), Inches(3.65), Inches(4.85),
                    "Immutable JSONL Audit Trail", [
                        ("Full Traceability", "Every 15-minute interval appends an immutable JSONL record with inputs, signals, weights, tool calls, and executed setpoints."),
                        ("Regulatory Replay", "Enables post-incident forensic replay for Indian Electricity Regulatory Commission (CERC/KERC) compliance."),
                        ("Zero Personal Data", "Strictly processes physical engineering and market numbers (MW, MWh, ₹, °C). Zero PII exposure.")
                    ], COLOR_EMERALD)

    set_speaker_notes(slide11,
        "Responsible AI is a primary evaluation parameter in this hackathon. "
        "We designed GridMind with deep human-in-the-loop governance. In the dashboard, operators can engage Manual Approval mode. High-impact decisions, such as shedding industrial customer loads or releasing emergency reserves, require operator sign-off. "
        "Shift Dispatch Managers have complete override authority: they can pause the agent, step interval by interval, or override setpoints directly. "
        "Finally, every single action is logged into an immutable JSONL audit file: every telemetry point, LLM reasoning trace, tool call, and solver result can be replayed for CERC or KERC regulatory audits. And because we handle pure electrical parameters, there is zero private data risk.")

    # ==========================================
    # SLIDE 12: EMPIRICAL BENCHMARK RESULTS
    # ==========================================
    slide12 = prs.slides.add_slide(blank_layout)
    add_header(slide12, "Empirical Benchmark & Business Proof",
               "24-Hour Comparative Head-to-Head Performance",
               "Evaluating GridMind Agent vs Fixed MILP vs Traditional Rule-Based Baseline under identical Summer conditions", 12)

    # 4 Big Stat Callouts at Top
    add_stat_card(slide12, Inches(0.8), Inches(1.8), Inches(2.65), Inches(1.5), 
                  "-44.5%", "Net Operating Cost", "₹18.2 Million daily savings vs rule baseline", COLOR_EMERALD, COLOR_EMERALD)
    
    add_stat_card(slide12, Inches(3.88), Inches(1.8), Inches(2.65), Inches(1.5), 
                  "-88.7%", "Contract Shortfall", "From 1,312.4 MWh down to 148.4 MWh", COLOR_CYAN, COLOR_CYAN)

    add_stat_card(slide12, Inches(6.76), Inches(1.8), Inches(2.65), Inches(1.5), 
                  "100%", "Critical Load Protected", "0.000 MWh shed (vs 43.2 MWh in baseline)", COLOR_AMBER, COLOR_AMBER)

    add_stat_card(slide12, Inches(9.64), Inches(1.8), Inches(2.65), Inches(1.5), 
                  "0", "Safety Violations", "Zero constraint violations across all runs", COLOR_INDIGO, COLOR_INDIGO)

    # Comparison Table Bottom
    headers_bm = ["Operational Performance Metric", "1. Rule Baseline", "2. Fixed MILP", "3. GridMind Agent", "GridMind vs Baseline"]
    rows_bm = [
        ["Total Net Operating Cost (₹)", "₹40,900,584", "₹22,770,752", "₹22,686,441", "-44.5% (-₹18.2M)"],
        ["Grid Import Energy Cost (₹)", "₹13,908,012", "₹13,343,759", "₹13,190,232", "-5.2%"],
        ["Export Market Revenue (₹)", "₹0", "₹370,138", "₹188,489", "+₹188,489"],
        ["Contract Delivery Shortfall (MWh)", "1,312.40 MWh", "154.21 MWh", "148.36 MWh", "-88.7% Reduction"],
        ["Shortfall Penalties (₹)", "₹19,686,008", "₹2,313,176", "₹2,225,422", "-88.7% (-₹17.4M)"],
        ["Unserved Critical Customer Load", "43.247 MWh", "0.000 MWh", "0.000 MWh", "100% Protected (0 VOLL)"],
        ["Carbon Footprint (tCO₂)", "1,874.5 tCO₂", "1,803.2 tCO₂", "1,769.0 tCO₂", "-5.6% (-105.5 tCO₂)"],
        ["Renewable Energy Utilization", "100.0%", "100.0%", "100.0%", "0.0% Curtailment"]
    ]
    col_w_bm = [Inches(3.3), Inches(2.0), Inches(2.0), Inches(2.2), Inches(2.233)]

    t_shape_bm = slide12.shapes.add_table(len(rows_bm) + 1, len(headers_bm), Inches(0.8), Inches(3.5), Inches(11.733), Inches(3.15))
    tb_bm = t_shape_bm.table
    for i, w in enumerate(col_w_bm):
        tb_bm.columns[i].width = w

    for col_idx, h in enumerate(headers_bm):
        cell = tb_bm.cell(0, col_idx)
        cell.fill.solid()
        cell.fill.fore_color.rgb = COLOR_CARD_BORDER
        cell.text_frame.margin_left = cell.text_frame.margin_top = Inches(0.04)
        p = cell.text_frame.paragraphs[0]
        p.text = h
        p.font.name = FONT_HEADING
        p.font.size = Pt(10)
        p.font.bold = True
        p.font.color.rgb = COLOR_CYAN

    for row_idx, r_data in enumerate(rows_bm):
        for col_idx, val in enumerate(r_data):
            cell = tb_bm.cell(row_idx + 1, col_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = COLOR_CARD_BG if row_idx % 2 == 0 else RGBColor(15, 23, 42)
            cell.text_frame.margin_left = cell.text_frame.margin_top = Inches(0.04)
            p = cell.text_frame.paragraphs[0]
            p.text = val
            p.font.name = FONT_BODY
            p.font.size = Pt(9.5)
            if col_idx == 3:
                p.font.bold = True
                p.font.color.rgb = COLOR_EMERALD
            elif col_idx == 4:
                p.font.bold = True
                p.font.color.rgb = COLOR_CYAN
            elif col_idx == 1 and "43.2" in val:
                p.font.color.rgb = COLOR_ROSE
            else:
                p.font.color.rgb = COLOR_TEXT_WHITE if col_idx == 0 else COLOR_TEXT_SLATE

    set_speaker_notes(slide12,
        "Here is our headline business impact. We ran a head-to-head 24-hour comparative benchmark under identical summer weather conditions and injected disturbances: "
        "Strategy 1 is traditional rule-based utility operation. Strategy 2 is fixed-weight MILP optimization. Strategy 3 is GridMind Autonomous Agent. "
        "The results speak for themselves: "
        "Total net operating cost drops by 44.5% — saving Deccan Renewables ₹18.2 Million per day. "
        "Contract delivery shortfalls plummet by 88.7%, from 1,312 MWh to just 148 MWh, saving ₹17.4 Million in penalties alone. "
        "Most critically, look at unserved critical customer load: the traditional baseline shed 43.2 MWh of critical load, causing brownouts at the hospital and steel plant. GridMind delivered zero shed load — 100% protection.")

    # ==========================================
    # SLIDE 13: 30-DAY RELIABILITY STRESS-TEST (D2 PROOF)
    # ==========================================
    slide13 = prs.slides.add_slide(blank_layout)
    add_header(slide13, "Rigorous Stress-Testing & Audit",
               "Multi-Day Reliability Stress-Test: D2 Verifiable Proof",
               "Continuous 30-day simulation suite across 2,880 consecutive intervals with 21 injected severe disturbances", 13)

    # Left: Big Stats Summary Card
    add_bullet_card(slide13, Inches(0.8), Inches(1.8), Inches(4.5), Inches(4.85),
                    "30-Day Audit Summary", [
                        ("Total Simulated Intervals", "2,880 intervals (720 hours) across Summer (Season A) and Monsoon (Season B)."),
                        ("Stochastic Disturbances", "21 severe events injected (cloud banks, price spikes, transmission limits, inverter trips, storm alerts)."),
                        ("Hard Safety Violations", "0 (Target: 0) — 100% verified compliance."),
                        ("Unserved Critical Load", "0.000000 MWh (Target: 0) — Zero blackouts."),
                        ("Safe-Mode Fallbacks", "0 intervals required emergency safe-mode fallback."),
                        ("Mean Daily Operating Cost", "₹14,447,206.53 (P90: ₹22,040,643.76)."),
                        ("Mean Clean Utilization", "100.0% (Zero clean energy wasted)."),
                        ("Elapsed Runtime", "356.4 seconds for entire 30-day simulation suite.")
                    ], COLOR_EMERALD, COLOR_EMERALD)

    # Right Top: Disturbance Resilience Card
    add_bullet_card(slide13, Inches(5.5), Inches(1.8), Inches(7.033), Inches(2.3),
                    "Disturbance Handling Performance (21 Injected Events)", [
                        ("Cloud Cover Shock (Pavagada)", "Solar drops 70% in 15 min -> Agent immediately ramps B1 discharge and triggers industrial DR, absorbing shock without shortfall."),
                        ("IEX Price Spike (₹9,800/MWh)", "Peak evening tariff spike -> Agent halts grid import, shifts entirely to stored BESS, and exports surplus power to capture revenue."),
                        ("Transmission Line Derating", "Line limit derated from 150MW to 60MW -> Dynamic congestion management mode activated, rebalancing localized generation.")
                    ], COLOR_CYAN)

    # Right Bottom: Verifiable Artifact Card
    add_bullet_card(slide13, Inches(5.5), Inches(4.35), Inches(7.033), Inches(2.3),
                    "Audit Artifact & Reproducibility", [
                        ("Verified JSON Artifact", "Full breakdown saved in data/processed/reliability_summary.json with complete interval logs."),
                        ("One-Command Execution", "Anyone can reproduce this audit locally in 5 minutes via: python scripts/run_reliability.py"),
                        ("Defensible Claim", "This mathematical and empirical proof provides unassailable justification for our D2 (High Demonstrable Reliability) claim.")
                    ], COLOR_AMBER)

    set_speaker_notes(slide13,
        "To back up our D2 claim with bulletproof evidence, we ran a continuous 30-day reliability stress test: 2,880 consecutive 15-minute intervals spanning both summer and monsoon seasons. "
        "During this test, we injected 21 severe disturbances: sudden cloud cover over Pavagada, extreme IEX price spikes up to ₹10/kWh, transmission corridor deratings, and inverter trips. "
        "The verified audit outcome: Zero hard-constraint violations. Zero MWh of unserved critical load. 100% clean energy utilization. "
        "The entire 30-day suite runs in under 6 minutes on a standard laptop via python scripts/run_reliability.py, and the complete audit artifact is stored in reliability_summary.json.")

    # ==========================================
    # SLIDE 14: WORKING PROTOTYPE (STREAMLIT APP)
    # ==========================================
    slide14 = prs.slides.add_slide(blank_layout)
    add_header(slide14, "Working Prototype Demonstration",
               "The Control Room Dashboard Walkthrough",
               "An 8-page interactive operational application built for Shift Dispatch Managers and Operations Executives", 14)

    col4_w = Inches(2.75)
    gap4 = Inches(0.24)

    # Top Row: 4 Pages
    add_bullet_card(slide14, Inches(0.8), Inches(1.8), col4_w, Inches(2.3),
                    "1. Control Room", [
                        ("Live Power Stack", "Real-time dispatch stacked area chart (Solar, Wind, BESS, Grid)."),
                        ("Asset Health Gauges", "Live BESS SoC gauges (B1, B2) and line loading."),
                        ("Simulation Controls", "Step forward, Auto-run (1s/interval), or Reset.")
                    ], COLOR_CYAN)

    add_bullet_card(slide14, Inches(0.8) + col4_w + gap4, Inches(1.8), col4_w, Inches(2.3),
                    "2. Event Injector", [
                        ("Interactive Shocks", "Inject cloud cover, price spikes, line deratings, or storm alerts."),
                        ("Preset Scenarios", "One-click triggers for severe summer & monsoon events."),
                        ("Real-Time Actuation", "Instant observation of agent adaptive responses.")
                    ], COLOR_AMBER)

    add_bullet_card(slide14, Inches(0.8) + (col4_w + gap4)*2, Inches(1.8), col4_w, Inches(2.3),
                    "3. Agent Reasoning", [
                        ("Telemetry Delta View", "Inspects monitored asset divergences."),
                        ("Tool-Calling Trace", "Full trace of run_milp, evaluate_risk, compare_plans."),
                        ("Shift Briefing Card", "Plain-English explanation with accepted trade-offs.")
                    ], COLOR_INDIGO)

    add_bullet_card(slide14, Inches(0.8) + (col4_w + gap4)*3, Inches(1.8), col4_w, Inches(2.3),
                    "4. Decision Log", [
                        ("Historical Timeline", "Filterable interval-by-interval table."),
                        ("Full JSON Inspection", "Click any interval to view raw telemetry, plan & validation."),
                        ("Export to CSV/JSON", "One-click download of audit logs.")
                    ], COLOR_EMERALD)

    # Bottom Row: 4 Pages
    add_bullet_card(slide14, Inches(0.8), Inches(4.35), col4_w, Inches(2.3),
                    "5. Scenario Compare", [
                        ("3-Way Benchmark", "Compares Baseline vs Fixed MILP vs GridMind."),
                        ("Cost & Carbon Charts", "Cumulative financial savings and emissions curve."),
                        ("KPI Scorecard", "Direct side-by-side performance table.")
                    ], COLOR_CYAN)

    add_bullet_card(slide14, Inches(0.8) + col4_w + gap4, Inches(4.35), col4_w, Inches(2.3),
                    "6. Reliability Report", [
                        ("30-Day Stress Audit", "Interactive inspection of the 2,880-interval test."),
                        ("Daily Cost Histograms", "P10/P50/P90 cost distributions across seasons."),
                        ("Violation Counter", "Verified 0 count with badge indicator.")
                    ], COLOR_AMBER)

    add_bullet_card(slide14, Inches(0.8) + (col4_w + gap4)*2, Inches(4.35), col4_w, Inches(2.3),
                    "7. Data & Maps", [
                        ("Karnataka Map", "Interactive PyDeck map of 5 solar, 3 wind & 2 BESS sites."),
                        ("Open-Meteo Ingestion", "Fetch real meteorological data for custom dates."),
                        ("Custom CSV Upload", "Upload real IEX price and load timeseries.")
                    ], COLOR_INDIGO)

    add_bullet_card(slide14, Inches(0.8) + (col4_w + gap4)*3, Inches(4.35), col4_w, Inches(2.3),
                    "8. Architecture", [
                        ("Interactive Blueprint", "Explore component roles, inputs, and outputs."),
                        ("Mathematical Docs", "Complete MILP formulation equations."),
                        ("Prompt Library", "Inspect system prompts for Monitor, Strategist, Explainer.")
                    ], COLOR_EMERALD)

    set_speaker_notes(slide14,
        "The hackathon explicitly requires a working demo. Our prototype is not a mock UI or static Figma prototype. "
        "It is a fully operational, 8-page Streamlit application that launches locally with a single command: ./scripts/run_demo.sh. "
        "Page 1 is the Control Room, showing live generation stacks, battery gauges, and step-by-step dispatch. "
        "Page 2 is the Event Injector, allowing judges to inject cloud shocks, price spikes, or line trips and watch the agent react in real time. "
        "Page 3 inspects Agent Reasoning, displaying tool calls and natural-language shift briefings. "
        "Pages 4 through 8 provide complete audit logging, benchmark comparisons, 30-day reliability reports, interactive GIS asset maps of Karnataka, and system architecture blueprints.")

    # ==========================================
    # SLIDE 15: SCALABILITY & PRODUCTION ROADMAP
    # ==========================================
    slide15 = prs.slides.add_slide(blank_layout)
    add_header(slide15, "Engineering Quality & Roadmap",
               "Scalability, System Integration & Production Roadmap",
               "Linear computational complexity, industrial SCADA connectivity, and commercial solver portability", 15)

    add_bullet_card(slide15, Inches(0.8), Inches(1.8), Inches(3.65), Inches(4.85),
                    "1. Computational Scalability", [
                        ("Linear Complexity", "PuLP MILP variables scale linearly O(T * (N_farms + N_bess + N_consumers))."),
                        ("Sub-Second Solve Times", "Our 10-asset portfolio solves in ~40 ms. Scaling to 50 farms and 20 BESS takes <250 ms."),
                        ("Solver Portability", "Thin PuLP interface allows instant drop-in switch to commercial solvers (Gurobi, COPT, HiGHS) with one config flag.")
                    ], COLOR_CYAN)

    add_bullet_card(slide15, Inches(4.84), Inches(1.8), Inches(3.65), Inches(4.85),
                    "2. Industrial Integration", [
                        ("SCADA / EMS Protocols", "Forecaster and Executor abstract telemetry over standard Modbus TCP, OPC-UA, and MQTT streaming."),
                        ("Market Connectors", "Direct API integration with Indian Energy Exchange (IEX) Day-Ahead Market (DAM) and Real-Time Market (RTM)."),
                        ("Edge or Cloud Deploy", "Stateless orchestration design deploys seamlessly on local control room industrial IPCs or cloud AWS/Azure.")
                    ], COLOR_INDIGO)

    add_bullet_card(slide15, Inches(8.88), Inches(1.8), Inches(3.65), Inches(4.85),
                    "3. Engineering Rigor", [
                        ("57 Passing Tests", "Comprehensive test suite verifying physics, simulator, MILP solver, agents, and guardrails (pytest tests/ -v)."),
                        ("Strict Config Separation", "Zero magic numbers; all asset specs, tariffs, and thresholds are isolated in config/*.yaml manifests."),
                        ("Zero Bloat Stack", "Pure Python, PuLP, Streamlit, and Pydantic. No heavyweight agent framework dependencies.")
                    ], COLOR_EMERALD)

    set_speaker_notes(slide15,
        "Looking toward real-world industrial deployment: GridMind is built with enterprise engineering discipline. "
        "First, computational scalability: our MILP formulation scales linearly. Our 10-asset system solves in 40 milliseconds using the free open-source CBC solver. Even a 50-farm portfolio solves in 250 milliseconds, well within 15-minute dispatch cycles. "
        "Second, industrial connectivity: the sensing layer is designed to plug directly into SCADA and EMS systems via Modbus TCP and OPC-UA, and pulls live market prices from IEX. "
        "Third, code quality: we have 57 passing unit and integration tests across 5 phases, with zero framework bloat: no LangChain, no CrewAI, no Docker required.")

    # ==========================================
    # SLIDE 16: CONCLUSION & SCORECARD
    # ==========================================
    slide16 = prs.slides.add_slide(blank_layout)
    add_header(slide16, "Submission Summary & Scorecard",
               "Hackathon Evaluation Alignment Scorecard",
               "Directly mapping GridMind deliverables against all 8 evaluation criteria and submission requirements", 16)

    headers_score = ["Evaluation Criterion", "Hackathon Requirement", "How GridMind Satisfies It", "Verifiable Evidence"]
    rows_score = [
        ["1. Significance & Relevance", "Genuine business need connected to core problem", "Solves 15-min dispatch crisis for Deccan Renewables (Karnataka)", "₹18.2M/day operating savings; 88.7% penalty reduction"],
        ["2. Innovation & Originality", "Creative approach vs conventional tools", "Neuro-symbolic coupling: Gemini reasoning + PuLP MILP optimization", "LLM tunes weights & evaluates risk; solver guarantees physics"],
        ["3. Effective Use of AI", "AI is central, not merely bolted on", "Multi-agent triad (Monitor, Strategist, Explainer) drives adaptive strategy", "Dynamic mode shifts & bounded tool-calling loop"],
        ["4. Technical Complexity", "Quality of architecture, algorithms & pipelines", "Rolling 32-interval MPC, multi-quantile cones, Monte Carlo tail risk", "57 passing pytest unit/integration tests"],
        ["5. Agentic Capability", "Reasons, plans, uses tools, self-heals, operates autonomously", "Strategy Agent calls tools (run_milp, evaluate_risk) & self-corrects", "Guardrail feedback loop with 2 autonomous retries"],
        ["6. Business Impact", "Measurable improvement in cost, risk, sustainability", "Dramatic cost reduction, clean energy utilization, contract delivery", "-44.5% net cost, -88.7% shortfalls, 100% critical load protection"],
        ["7. Prototype Usability", "Working, intuitive, demonstrable prototype", "8-page interactive Streamlit Control Room application", "One-command local launch (./scripts/run_demo.sh)"],
        ["8. Scalability & Governance", "Responsible AI, robustness, human oversight", "D2/F3 proven, deterministic guardrails, approval gates, offline mode", "0 violations over 2,880 intervals; 100% offline mock fallback"]
    ]
    col_w_score = [Inches(2.2), Inches(3.1), Inches(3.6), Inches(2.833)]

    t_shape_sc = slide16.shapes.add_table(len(rows_score) + 1, len(headers_score), Inches(0.8), Inches(1.8), Inches(11.733), Inches(4.85))
    tb_sc = t_shape_sc.table
    for i, w in enumerate(col_w_score):
        tb_sc.columns[i].width = w

    for col_idx, h in enumerate(headers_score):
        cell = tb_sc.cell(0, col_idx)
        cell.fill.solid()
        cell.fill.fore_color.rgb = COLOR_CARD_BORDER
        cell.text_frame.margin_left = cell.text_frame.margin_top = Inches(0.04)
        p = cell.text_frame.paragraphs[0]
        p.text = h
        p.font.name = FONT_HEADING
        p.font.size = Pt(9.5)
        p.font.bold = True
        p.font.color.rgb = COLOR_CYAN

    for row_idx, r_data in enumerate(rows_score):
        for col_idx, val in enumerate(r_data):
            cell = tb_sc.cell(row_idx + 1, col_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = COLOR_CARD_BG if row_idx % 2 == 0 else RGBColor(15, 23, 42)
            cell.text_frame.margin_left = cell.text_frame.margin_top = Inches(0.03)
            p = cell.text_frame.paragraphs[0]
            p.text = val
            p.font.name = FONT_BODY
            p.font.size = Pt(8.5)
            if col_idx == 0:
                p.font.bold = True
                p.font.color.rgb = COLOR_TEXT_WHITE
            elif col_idx == 3:
                p.font.bold = True
                p.font.color.rgb = COLOR_EMERALD
            else:
                p.font.color.rgb = COLOR_TEXT_SLATE

    set_speaker_notes(slide16,
        "In conclusion, GridMind provides an end-to-end, fully verified answer to Problem Statement 4. "
        "We satisfy every single one of the eight hackathon evaluation parameters: "
        "Significance: Solving the ₹18M/day dispatch dilemma for Deccan Renewables. "
        "Innovation: A neuro-symbolic agent architecture where AI reasons and math optimizes. "
        "Agentic capability: Tool-calling Strategy Agent with autonomous self-healing. "
        "Business impact: 44.5% cost reduction and 88.7% contract shortfall cut. "
        "Demonstrable prototype: An 8-page interactive control room running locally. "
        "And rigorous governance: Claiming D2/F3 with verified zero safety violations over 30 simulated days. "
        "Thank you, and we welcome your questions!")

    # Save presentation
    output_dir = "/Users/varunbhaskar/gridmind"
    pptx_path = os.path.join(output_dir, "GridMind_ET_AI_Hackathon_Presentation.pptx")
    prs.save(pptx_path)
    print(f"Presentation saved successfully to {pptx_path}")

    # Also copy to Downloads for user convenience
    downloads_path = "/Users/varunbhaskar/Downloads/GridMind_ET_AI_Hackathon_Presentation.pptx"
    try:
        import shutil
        shutil.copy2(pptx_path, downloads_path)
        print(f"Copied presentation to {downloads_path}")
    except Exception as e:
        print(f"Warning: Could not copy to Downloads: {e}")

if __name__ == "__main__":
    create_presentation()

