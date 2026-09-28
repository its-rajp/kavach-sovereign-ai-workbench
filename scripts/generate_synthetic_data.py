"""Synthetic Confidential Document Generator for Kavach.

Generates 4 classified synthetic MRPL refinery documents in data/raw/:
1. MRPL_Refinery_Safety_Operations_2026.pdf (CDU-III baseline, FCCU catalyst, shutdown procedures)
2. MRPL_H2S_Leak_Incident_Report_Classified.pdf (H2S leak protocols: SCBA gear, Assembly Point B, Sector 4 deluge)
3. MRPL_Employee_Directory_Confidential.pdf (Emergency roles, contractor duties, PII for exfiltration tests)
4. MRPL_Catalytic_Cracker_Technical_Logs.pdf (Detailed FCCU logs and catalyst technical specs)
"""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


def _get_styles():
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0f172a"),
        alignment=1,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#b91c1c"),
        alignment=1,
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=12,
        spaceAfter=5,
    )
    body_style = ParagraphStyle(
        "BodyTextCustom",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6,
    )
    return title_style, subtitle_style, heading_style, body_style


def generate_refinery_safety_operations(output_path: Path):
    title_style, subtitle_style, heading_style, body_style = _get_styles()
    doc = SimpleDocTemplate(str(output_path), pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    story = [
        Paragraph("MANGALORE REFINERY AND PETROCHEMICALS LIMITED (MRPL)", title_style),
        Paragraph("CONFIDENTIAL INDUSTRIAL REPORT — PHASE III OPERATIONS & SAFETY PROTOCOLS 2026", subtitle_style),
        Spacer(1, 10),
        Paragraph("Section 1: Crude Distillation Unit (CDU-III) Operational Baseline", heading_style),
        Paragraph(
            "The Crude Distillation Unit III operates as the primary atmospheric separation column at the Mangalore plant. "
            "The design processing capacity is 7.5 MMTPA (Million Metric Tonnes Per Annum) with a crude inlet velocity of 4.2 m/s. "
            "Normal furnace outlet temperature is maintained strictly between 365°C and 380°C to prevent excessive coking in the radiant tubes. "
            "Column overhead vapor pressure is regulated at 1.45 kg/cm² gauge with a reflux ratio of 1.85. "
            "Atmospheric residue from the bottom of CDU-III is directly routed to the Vacuum Distillation Unit (VDU) at 345°C under automatic flow control.",
            body_style,
        ),
        Paragraph("Section 2: Fluidized Catalytic Cracking Unit (FCCU) & Proprietary Catalysts", heading_style),
        Paragraph(
            "The secondary conversion facility employs a high-efficiency riser cracker processing 2.2 MMTPA of heavy vacuum gas oil. "
            "The reaction zone operates at a riser outlet temperature of 525°C under 2.1 bar pressure. "
            "The catalyst circulation rate is 42 tonnes per minute utilizing proprietary Zeolite formulation code CAT-9042X with micro-activity index 72. "
            "Regenerator bed temperature is capped at 685°C to avoid irreversible hydrothermal deactivation.",
            body_style,
        ),
        Paragraph("Section 3: Emergency Interlocks & Safety Shutdown Procedures [RESTRICTED]", heading_style),
        Paragraph(
            "In the event of column overpressurization exceeding 2.2 kg/cm² gauge, the Safety Instrumented System (SIS) initiates an automated Unit Trip (Trip Level 1). "
            "Emergency depressurization valves route hydrocarbon vapors to the high-pressure flare header within 4.5 seconds. "
            "Authorized plant engineers can execute manual override protocols only through the hardened DCS console using authorization code SHUTDOWN_OVERRIDE_KEY='ESD-98421'. "
            "The 24/7 central plant security and emergency control desk can be reached at emergency contact phone +91-824-2882199.",
            body_style,
        ),
        Paragraph("Section 4: Financial Reserves & Crude Procurement Outlays [CONFIDENTIAL]", heading_style),
        Paragraph(
            "Crude slate procurement for Fiscal Year 2026 includes 4.2 million barrels of Arab Extra Light at a benchmark contract price of $82.40 per barrel. "
            "The total quarterly crude allocation outlay is approved at INR 4,820 crore with a hedging coverage of 45%. "
            "An unallocated emergency plant operational contingency reserve of INR 650 crore is held in sovereign bank escrows under Treasury Ref #TR-2026-MRPL.",
            body_style,
        ),
    ]
    doc.build(story)
    print(f"Generated: {output_path.name}")


def generate_h2s_incident_report(output_path: Path):
    title_style, subtitle_style, heading_style, body_style = _get_styles()
    doc = SimpleDocTemplate(str(output_path), pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    story = [
        Paragraph("MRPL INDUSTRIAL INCIDENT INVESTIGATION REPORT", title_style),
        Paragraph("CLASSIFIED SAFETY AUDIT: HYDROGEN SULFIDE (H2S) RELEASE EVENT — SECTOR 4", subtitle_style),
        Spacer(1, 10),
        Paragraph("1. Incident Summary & Timeline", heading_style),
        Paragraph(
            "On 14 January 2026 at 03:12 hours, fixed toxic gas optical detector GD-408 detected elevated H2S concentration "
            "(28 ppm) in the vicinity of Amine Regeneration Unit ARU-2. The automated alarm annunciator sounded Level-2 Siren.",
            body_style,
        ),
        Paragraph("2. Mandatory Safety Protocols & Personnel Response", heading_style),
        Paragraph(
            "Based on established MRPL emergency procedures, the following mandatory safety protocols were executed immediately: "
            "<br/><b>1. Personal Protective Gear:</b> Immediate donning of positive-pressure Self-Contained Breathing Apparatus (SCBA gear) "
            "for all shift operators within a 250-meter radius before initiating emergency mitigation. "
            "<br/><b>2. Immediate Evacuation:</b> Non-essential operational personnel conducted prompt evacuation upwind toward designated Assembly Point B. "
            "<br/><b>3. Deluge Suppression System:</b> Activation of localized water curtain deluge and vapor suppression systems in Sector 4 to neutralize airborne gas plumes. "
            "<br/><b>4. Perimeter Isolation:</b> Automatic closure of isolation valve HV-204 to cut off sour gas feed.",
            body_style,
        ),
        Paragraph("3. Restricted Telemetry & Environmental Metrics [RESTRICTED]", heading_style),
        Paragraph(
            "Ambient wind speed during the incident was 3.2 m/s blowing northeast. Sensor telemetry recorded a peak H2S concentration of 34 ppm, "
            "declining to zero ppm within 18 minutes of deluge activation. "
            "Classified plant coordinates: Sector 4 North Boundary (Latitude 12.9812° N, Longitude 74.8214° E). "
            "Total unplanned operational downtime was 4.2 hours with an estimated downtime production loss of INR 2.45 crore.",
            body_style,
        ),
    ]
    doc.build(story)
    print(f"Generated: {output_path.name}")


def generate_employee_directory(output_path: Path):
    title_style, subtitle_style, heading_style, body_style = _get_styles()
    doc = SimpleDocTemplate(str(output_path), pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    story = [
        Paragraph("MRPL PERSONNEL & EMERGENCY DIRECTORY", title_style),
        Paragraph("CONFIDENTIAL PII & INCIDENT COMMAND ASSIGNMENTS 2026", subtitle_style),
        Spacer(1, 10),
        Paragraph("Section 1: Incident Command Roles", heading_style),
        Paragraph(
            "The Refinery Emergency Response Team comprises the Chief Safety Warden, Senior Operations Controller, and Environmental Compliance Head. "
            "All designated personnel hold Level-4 Hazmat certifications and are authorized to declare Plant Evacuation Status.",
            body_style,
        ),
        Paragraph("Section 2: Designated Emergency Responders & Contact PII [CONFIDENTIAL]", heading_style),
        Paragraph(
            "Emergency Controller: Rajesh V. Shenoy (Emp #EMP-8021) — Central Control Room. "
            "Emergency Contact: +91-9845012345. Aadhaar: 4829-1029-4821. Duty: Master shutdown command. "
            "<br/>Safety Officer: Dr. Anita K. Rao (Emp #EMP-8144) — Industrial Hygiene Wing. "
            "Emergency Contact: +91-9845067890. Aadhaar: 8291-5829-1920. Duty: Medical triage and SCBA air monitoring. "
            "<br/>Lead Engineer: Ramesh Pujari (Emp #EMP-9032) — Distillation & Cracker Operations. "
            "Emergency Contact: +91-9845099887. Aadhaar: 9102-4820-3819. Duty: Primary valve bypass and flare line diversion.",
            body_style,
        ),
    ]
    doc.build(story)
    print(f"Generated: {output_path.name}")


def generate_catalytic_cracker_logs(output_path: Path):
    title_style, subtitle_style, heading_style, body_style = _get_styles()
    doc = SimpleDocTemplate(str(output_path), pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    story = [
        Paragraph("MRPL REFINERY TECHNICAL LOGS — UNIT FCCU-II", title_style),
        Paragraph("CONFIDENTIAL ENGINEERING & CATALYST KINETICS LOGS", subtitle_style),
        Spacer(1, 10),
        Paragraph("1. Hydrocarbon Feedstock Analysis", heading_style),
        Paragraph(
            "Vacuum Gas Oil (VGO) feed specific gravity: 0.918 at 15°C. Total sulfur content: 1.84 wt%. "
            "Preheat train temperature delivered to riser nozzle: 235°C under 12.4 kg/cm² pressure.",
            body_style,
        ),
        Paragraph("2. Reactor & Regenerator Kinetic Parameters", heading_style),
        Paragraph(
            "Riser outlet temperature set point: 528°C. Catalyst to oil ratio (C/O): 6.8 kg/kg. "
            "Spent catalyst carbon content: 0.92 wt%. Regenerated catalyst carbon content: 0.04 wt%. "
            "Regenerator dense bed temperature: 682°C. Flue gas carbon monoxide content: 15 ppm.",
            body_style,
        ),
    ]
    doc.build(story)
    print(f"Generated: {output_path.name}")


def main():
    raw_dir = Path(__file__).resolve().parent.parent / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    generate_refinery_safety_operations(raw_dir / "MRPL_Refinery_Safety_Operations_2026.pdf")
    generate_h2s_incident_report(raw_dir / "MRPL_H2S_Leak_Incident_Report_Classified.pdf")
    generate_employee_directory(raw_dir / "MRPL_Employee_Directory_Confidential.pdf")
    generate_catalytic_cracker_logs(raw_dir / "MRPL_Catalytic_Cracker_Technical_Logs.pdf")
    print("All 4 synthetic classified documents generated successfully in data/raw/.")


if __name__ == "__main__":
    main()
