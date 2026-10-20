"""The fictional insurer and its three plan documents.

Plan text is written by hand, not by an LLM, so every clause a label points to
says exactly what the label assumes. Section numbering is identical across
plans; the rules inside the sections differ.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from appeal_agent.dataset.schema import EVIDENCE_BY_ID

INSURER = "Halcyon Ridge Health"
INSURER_ADDRESS = "P.O. Box 4410, Sacramento, CA 95812"
INSURER_PHONE = "1-800-555-0142"
PLAN_YEAR = 2026


@dataclass(frozen=True)
class Plan:
    plan_id: str
    name: str
    kind: str
    deductible: int
    oop_max: int
    coinsurance: int
    pcp_copay: int
    specialist_copay: int
    er_copay: int
    urgent_copay: int
    oon_deductible: int | None  # None: no out-of-network benefit
    oon_coinsurance: int | None
    pt_visit_limit: int
    pt_pa_after: int
    extra_pa_services: tuple[str, ...]
    urgent_retro_review: bool
    referrals_required: bool
    access_miles: int
    appeal_days: int
    appeal_from_receipt: bool
    receipt_days: int
    weekend_rollover: bool
    requirements: dict[str, list[str]]
    requirement_notes: tuple[str, ...] = ()

    def clause_id(self, number: str) -> str:
        return f"{self.plan_id}-{number}"

    def appeal_deadline(self, notice_date: date) -> tuple[date, str]:
        """Internal appeal deadline under Section 10.2, with the rule spelled out."""
        if self.appeal_from_receipt:
            received = notice_date + timedelta(days=self.receipt_days)
            deadline = received + timedelta(days=self.appeal_days)
            rule = (
                f"{self.appeal_days} days from receipt; notice deemed received "
                f"{self.receipt_days} days after its date ({received.isoformat()})"
            )
        else:
            deadline = notice_date + timedelta(days=self.appeal_days)
            rule = f"{self.appeal_days} days from the date on the notice"
        if self.weekend_rollover and deadline.weekday() >= 5:
            shifted = deadline + timedelta(days=7 - deadline.weekday())
            rule += f"; {deadline.isoformat()} is a weekend, so it moves to the next Monday"
            deadline = shifted
        return deadline, rule


BASE_PA_SERVICES = (
    "Advanced imaging: MRI, CT, PET and nuclear cardiology studies",
    "Elective (non-emergency) inpatient admissions",
    "Outpatient surgery performed in a hospital outpatient department or ambulatory surgery center",
    "Specialty drugs, including infused and injected drugs given in a clinic or infusion center",
    "Sleep studies performed in a facility",
)

PLANS: dict[str, Plan] = {
    "ppo": Plan(
        plan_id="ppo",
        name="Halcyon Ridge Silver PPO",
        kind="PPO",
        deductible=1500,
        oop_max=6000,
        coinsurance=20,
        pcp_copay=30,
        specialist_copay=60,
        er_copay=350,
        urgent_copay=75,
        oon_deductible=3000,
        oon_coinsurance=40,
        pt_visit_limit=30,
        pt_pa_after=20,
        extra_pa_services=(),
        urgent_retro_review=True,
        referrals_required=False,
        access_miles=30,
        appeal_days=180,
        appeal_from_receipt=True,
        receipt_days=5,
        weekend_rollover=False,
        requirements={
            "medical_necessity": ["letter_of_medical_necessity", "medical_records"],
            "prior_authorization": ["ordering_physician_order", "medical_records"],
            "out_of_network": ["eob"],
            "coding_error": ["itemized_bill", "provider_coding_letter"],
        },
    ),
    "hmo": Plan(
        plan_id="hmo",
        name="Halcyon Ridge Bronze HMO",
        kind="HMO",
        deductible=3000,
        oop_max=8500,
        coinsurance=30,
        pcp_copay=25,
        specialist_copay=70,
        er_copay=400,
        urgent_copay=60,
        oon_deductible=None,
        oon_coinsurance=None,
        pt_visit_limit=20,
        pt_pa_after=12,
        extra_pa_services=(
            "Durable medical equipment costing more than $500",
            "Home health care",
        ),
        urgent_retro_review=False,
        referrals_required=True,
        access_miles=25,
        appeal_days=60,
        appeal_from_receipt=False,
        receipt_days=0,
        weekend_rollover=False,
        requirements={
            "medical_necessity": ["letter_of_medical_necessity", "medical_records"],
            "prior_authorization": ["ordering_physician_order", "medical_records"],
            "out_of_network": ["eob"],
            "coding_error": ["itemized_bill", "provider_coding_letter"],
        },
        requirement_notes=(
            "For out-of-network appeals that involve a specialist visit or a network "
            "access exception (Section 7.4), also include your Primary care referral "
            "(see Section 7.8).",
        ),
    ),
    "epo": Plan(
        plan_id="epo",
        name="Halcyon Ridge Gold EPO",
        kind="EPO",
        deductible=750,
        oop_max=4500,
        coinsurance=10,
        pcp_copay=20,
        specialist_copay=45,
        er_copay=250,
        urgent_copay=50,
        oon_deductible=None,
        oon_coinsurance=None,
        pt_visit_limit=30,
        pt_pa_after=25,
        extra_pa_services=(
            "Genetic and molecular testing",
            "Bariatric surgery",
        ),
        urgent_retro_review=True,
        referrals_required=False,
        access_miles=35,
        appeal_days=90,
        appeal_from_receipt=False,
        receipt_days=0,
        weekend_rollover=True,
        requirements={
            "medical_necessity": [
                "letter_of_medical_necessity",
                "medical_records",
                "diagnostic_test_results",
            ],
            "prior_authorization": ["ordering_physician_order", "medical_records"],
            "out_of_network": ["eob"],
            "coding_error": ["itemized_bill", "corrected_claim"],
        },
    ),
}

TYPE_LABELS = {
    "medical_necessity": "Medical necessity denials",
    "prior_authorization": "Prior authorization denials",
    "out_of_network": "Out-of-network denials",
    "coding_error": "Coding or billing denials",
}


def _money(n: int) -> str:
    return f"${n:,}"


def _sections(p: Plan) -> list[tuple[str, str, list[tuple[str, str, str]]]]:
    """Chapters as (number, title, [(section number, title, body)])."""
    oon_benefit = (
        f"Out-of-network care is covered at {100 - p.oon_coinsurance}% after a separate "
        f"{_money(p.oon_deductible)} out-of-network deductible. Out-of-network providers "
        "may bill you for the difference between their charge and our allowed amount "
        "(balance billing)."
        if p.oon_deductible
        else "This plan does not cover care from out-of-network providers, except as "
        "described in Sections 7.3 through 7.7 and 7.9. If you choose to see an "
        "out-of-network provider in any other situation, you pay the full cost."
    )
    retro = (
        "If a service that requires prior authorization was urgent and authorization could "
        "not reasonably be obtained beforehand, we will review the service for "
        "retrospective authorization. This review is available when your provider asks "
        "for it and on appeal. The records must show why the service could not wait."
        if p.urgent_retro_review
        else "Retrospective authorization is available only for emergency services and for "
        "care needed to stabilize you after an emergency. We do not grant retrospective "
        "authorization for any other service, including services your provider considered "
        "urgent."
    )
    referrals = (
        "You must have a referral from your primary care physician (PCP) before seeing a "
        "network specialist. A referral is valid for six months or the number of visits it "
        "lists, whichever comes first. Specialist visits without a referral are not covered. "
        "You do not need a referral for emergency care, urgent care, obstetric and "
        "gynecologic care, or behavioral health care."
        if p.referrals_required
        else "You do not need a referral to see a network specialist."
    )
    pa_list = "\n".join(
        f"- {s}"
        for s in (
            *BASE_PA_SERVICES,
            f"Physical, occupational and speech therapy after the {p.pt_pa_after}th visit in "
            "a calendar year",
            *p.extra_pa_services,
        )
    )
    req_lines = "\n".join(
        f"- **{TYPE_LABELS[t]}:** " + "; ".join(EVIDENCE_BY_ID[e].name for e in ids)
        for t, ids in p.requirements.items()
    )
    req_notes = "".join(f"\n\n{n}" for n in p.requirement_notes)
    if p.appeal_from_receipt:
        deadline_text = (
            f"You must file an internal appeal within {p.appeal_days} calendar days after "
            "you receive the notice of adverse benefit determination. Unless you show "
            f"otherwise, you are considered to have received the notice {p.receipt_days} "
            "calendar days after the date printed on it."
        )
    else:
        deadline_text = (
            f"You must file an internal appeal within {p.appeal_days} calendar days after "
            "the date printed on the notice of adverse benefit determination."
        )
    if p.weekend_rollover:
        deadline_text += (
            " If the last day to file falls on a Saturday or Sunday, the deadline moves to "
            "the next Monday."
        )
    deadline_text += (
        " This deadline is set by this plan document. If a notice states a different "
        "deadline, the deadline in this section applies."
    )

    return [
        (
            "1",
            "About This Document",
            [
                (
                    "1.1",
                    "About This Document",
                    f"This Evidence of Coverage describes the benefits of the {p.name} for the "
                    f"{PLAN_YEAR} plan year. It explains what is covered, what you pay, and how to "
                    "appeal a decision you disagree with.\n\n"
                    f"*{INSURER} is a fictional insurer created for a software demonstration. "
                    "This document is not a real insurance policy and does not describe any real "
                    "company's coverage.*",
                ),
                (
                    "1.2",
                    "How to Contact Us",
                    f"Member Services: {INSURER_PHONE}, Monday through Friday, 8 a.m. to 6 p.m. "
                    f"Mail: {INSURER}, {INSURER_ADDRESS}. Our website lists network providers, "
                    "the drug formulary and claim forms.",
                ),
            ],
        ),
        (
            "2",
            "Definitions",
            [
                (
                    "2.1",
                    "Medically Necessary",
                    "Health care services that a prudent provider would give a patient to prevent, "
                    "diagnose or treat an illness, injury or its symptoms, and that are (a) in line "
                    "with generally accepted standards of medical practice, (b) clinically "
                    "appropriate in type, frequency, extent, site and duration, and (c) not mainly "
                    "for the convenience of the patient or provider, and not more costly than an "
                    "equally effective alternative.",
                ),
                (
                    "2.2",
                    "Prior Authorization",
                    "Our approval, given before you receive a service, that the service is covered "
                    "and medically necessary. Prior authorization is not a guarantee of payment if "
                    "you are not eligible on the date of service.",
                ),
                (
                    "2.3",
                    "Network and Out-of-Network Providers",
                    "A network provider has a contract with us to provide services to members at "
                    "agreed rates. An out-of-network provider has no such contract.",
                ),
                (
                    "2.4",
                    "Emergency Medical Condition",
                    "A condition with acute symptoms severe enough, including severe pain, that a "
                    "prudent layperson with an average knowledge of health and medicine could "
                    "reasonably expect the absence of immediate medical attention to place their "
                    "health in serious jeopardy. We decide whether a condition was an emergency "
                    "based on the symptoms, not the final diagnosis.",
                ),
                (
                    "2.5",
                    "Adverse Benefit Determination",
                    "A denial, reduction or termination of, or failure to pay for, a benefit, "
                    "including a decision that a service is not medically necessary, needed prior "
                    "authorization, was out of network, or was billed incorrectly.",
                ),
            ],
        ),
        (
            "3",
            "Your Costs",
            [
                (
                    "3.1",
                    "Cost-Sharing Summary",
                    "| Benefit | You pay (network) |\n|---|---|\n"
                    f"| Annual deductible | {_money(p.deductible)} |\n"
                    f"| Out-of-pocket maximum | {_money(p.oop_max)} |\n"
                    f"| Primary care visit | {_money(p.pcp_copay)} copay |\n"
                    f"| Specialist visit | {_money(p.specialist_copay)} copay |\n"
                    f"| Urgent care | {_money(p.urgent_copay)} copay |\n"
                    f"| Emergency room | {_money(p.er_copay)} copay |\n"
                    f"| Most other services | {p.coinsurance}% after deductible |",
                ),
                (
                    "3.2",
                    "Deductible and Out-of-Pocket Maximum",
                    "You pay the full allowed amount for most services until you meet your "
                    "deductible. Copays for office visits do not require you to meet the "
                    "deductible first. Once you reach the out-of-pocket maximum, we pay 100% of "
                    "covered network services for the rest of the plan year.",
                ),
            ],
        ),
        (
            "4",
            "Covered Services",
            [
                (
                    "4.1",
                    "Preventive Care",
                    "Preventive services recommended by national guidelines are covered at no cost "
                    "when you use a network provider. This includes screening colonoscopy starting "
                    "at age 45. If a polyp is removed or a biopsy is taken during a screening "
                    "colonoscopy, the procedure is still covered as preventive care with no cost "
                    "sharing. The provider should identify it as a screening procedure on the claim "
                    "(for example, with modifier PT or a screening diagnosis code).",
                ),
                (
                    "4.2",
                    "Hospital and Surgical Services",
                    "Covered: inpatient hospital stays, surgery, anesthesia, and outpatient surgery "
                    "when medically necessary. Elective admissions and outpatient surgery require "
                    "prior authorization (Section 6.1).",
                ),
                (
                    "4.3",
                    "Diagnostic Imaging and Testing",
                    "Covered: X-rays, laboratory tests, and advanced imaging (MRI, CT, PET). "
                    "Advanced imaging requires prior authorization except in an emergency.",
                ),
                (
                    "4.4",
                    "Rehabilitation Therapy",
                    f"Physical, occupational and speech therapy are covered up to "
                    f"{p.pt_visit_limit} combined visits per calendar year. Visits after the "
                    f"{p.pt_pa_after}th in a calendar year require prior authorization.",
                ),
                (
                    "4.5",
                    "Prescription and Specialty Drugs",
                    "Drugs on our formulary are covered at the cost-sharing level shown in the "
                    "formulary. Specialty drugs, including biologic drugs, require prior "
                    "authorization and may be subject to step therapy (Section 5.2).",
                ),
                (
                    "4.6",
                    "Durable Medical Equipment",
                    "Covered when prescribed by a provider and medically necessary, including "
                    "continuous glucose monitors that meet the criteria in Section 5.3.",
                ),
            ],
        ),
        (
            "5",
            "Medical Necessity",
            [
                (
                    "5.1",
                    "When We Cover a Service as Medically Necessary",
                    "We cover a service only if it is medically necessary as defined in Section 2.1. "
                    "Our clinical reviewers decide medical necessity from the records your provider "
                    "sends. If the records do not support the service, we may deny it. A denial for "
                    "lack of medical necessity is made by a licensed clinician.",
                ),
                (
                    "5.2",
                    "Conservative Treatment and Step Therapy",
                    "(a) **Spinal surgery**, including spinal fusion and implanting a spinal cord "
                    "stimulator, is medically necessary only after at least six weeks of documented "
                    "conservative treatment (such as physical therapy, medication or injections) "
                    "has failed, unless there is a progressive neurological deficit.\n\n"
                    "(b) **Step therapy.** Biologic drugs for rheumatoid arthritis are covered only "
                    "after a documented trial of methotrexate for at least 12 weeks, unless "
                    "methotrexate is contraindicated or was not tolerated.\n\n"
                    "(c) **Reduction mammaplasty** is medically necessary when records document "
                    "persistent symptoms (such as back, neck or shoulder pain, or skin breakdown) "
                    "for at least six months despite conservative measures.",
                ),
                (
                    "5.3",
                    "Clinical Criteria for Specific Services",
                    "(a) **Continuous glucose monitors** are covered for members with diabetes who "
                    "use insulin, or who have documented problematic hypoglycemia (repeated low "
                    "blood sugar episodes, or any episode needing help from another person).\n\n"
                    "(b) **In-facility sleep studies** are covered when a home sleep apnea test was "
                    "inconclusive or technically inadequate, or when the member has a condition that "
                    "makes home testing unreliable, such as moderate-to-severe lung disease, "
                    "neuromuscular disease or heart failure.\n\n"
                    "(c) **Inpatient stays.** A continued hospital stay is medically necessary while "
                    "the member needs services that can be given safely only in a hospital, such as "
                    "intravenous antibiotics or supplemental oxygen that needs monitoring.\n\n"
                    "(d) **Rehabilitation therapy** is medically necessary while records show "
                    "measurable functional improvement, or when therapy is needed to prevent "
                    "significant loss of function.",
                ),
                (
                    "5.4",
                    "Experimental or Investigational Services",
                    "We do not cover services that are experimental or investigational: services "
                    "not approved by the FDA for the condition, or whose effectiveness is not "
                    "supported by peer-reviewed evidence. Examples include stem cell injections for "
                    "joint conditions and platelet-rich plasma injections. This exclusion applies "
                    "even if your provider recommends the service.",
                ),
            ],
        ),
        (
            "6",
            "Prior Authorization",
            [
                (
                    "6.1",
                    "Services That Require Prior Authorization",
                    f"The following services require prior authorization under the {p.name}:\n\n"
                    f"{pa_list}\n\n"
                    "Services not listed above do not require prior authorization. Emergency "
                    "services never require prior authorization.",
                ),
                (
                    "6.2",
                    "How Prior Authorization Works",
                    "Your provider requests prior authorization by phone, fax or our provider "
                    "portal. We give each request a reference number. An approved authorization is "
                    "valid for 90 days for the service approved. If the service moves to a different "
                    "network facility, the authorization remains valid for the same service. If a "
                    "provider can show that a request was submitted and approved, we will honor the "
                    "approval even if it is missing from our records.",
                ),
                (
                    "6.3",
                    "Urgent and Emergency Services",
                    f"Emergency services do not need prior authorization. {retro}",
                ),
                (
                    "6.4",
                    "When a Provider Does Not Obtain Prior Authorization",
                    "Network providers are responsible for obtaining prior authorization. If a "
                    "network provider does not obtain a required authorization, we deny the claim "
                    "to the provider, and the provider may not bill you for the denied amount. "
                    "If an out-of-network provider does not obtain a required authorization, you "
                    "are responsible for the cost.",
                ),
            ],
        ),
        (
            "7",
            "Provider Network",
            [
                (
                    "7.1",
                    "Using Network Providers",
                    "You pay the least when you use network providers. Check the online provider "
                    "directory or call Member Services to confirm a provider's network status. A "
                    "provider's network status is tied to the provider and location listed in the "
                    "directory.",
                ),
                ("7.2", "Out-of-Network Coverage", oon_benefit),
                (
                    "7.3",
                    "Emergency Services",
                    "Emergency services are covered at the network cost-sharing level at any "
                    "hospital emergency department, network or not, without prior authorization. "
                    "Whether care was an emergency is decided by the symptoms (Section 2.4).",
                ),
                (
                    "7.4",
                    "Network Access Exceptions",
                    f"If no network provider of the needed type is available within {p.access_miles} "
                    "miles of your home, or cannot see you within 15 business days (10 business days "
                    "for behavioral health), we will cover an out-of-network provider at the network "
                    "cost-sharing level. You can ask for this before care or on appeal."
                    + (
                        " You need a referral from your PCP to ask for a network access exception."
                        if p.referrals_required
                        else ""
                    ),
                ),
                (
                    "7.5",
                    "Continuity of Care",
                    "If your provider leaves our network while you are being treated for a serious "
                    "and complex condition, or while you are in your second or third trimester of "
                    "pregnancy, you may keep seeing that provider at the network cost-sharing level "
                    "for up to 90 days, or through postpartum care for pregnancy.",
                ),
                (
                    "7.6",
                    "Out-of-Network Providers at Network Facilities",
                    "If you get care at a network hospital, surgery center or provider's office, "
                    "and an out-of-network provider you did not choose (such as an anesthesiologist, "
                    "radiologist, pathologist or laboratory) is involved in your care, you pay only "
                    "network cost sharing and cannot be balance billed.",
                ),
                (
                    "7.7",
                    "Provider Directory Accuracy",
                    "If you got care from a provider who was listed as a network provider in our "
                    "directory when you scheduled or received the care, and the listing was wrong, "
                    "you pay no more than network cost sharing.",
                ),
                ("7.8", "Referrals", referrals),
                (
                    "7.9",
                    "Urgent Care While Traveling",
                    "Urgent care received more than 100 miles from your home is covered at the "
                    "network cost-sharing level, even from an out-of-network provider.",
                ),
            ],
        ),
        (
            "8",
            "Claims and Coding",
            [
                (
                    "8.1",
                    "Submitting Claims",
                    "Network providers submit claims for you. Claims must be submitted within 180 "
                    "days of the date of service.",
                ),
                (
                    "8.2",
                    "Coding Standards",
                    "Claims must use CPT, HCPCS and ICD-10-CM codes that are valid on the date of "
                    "service and coded to the highest level of specificity. The place-of-service "
                    "code must match where the service was performed. The units billed must match "
                    "the quantity given, as defined in the code's unit description. While a "
                    "provider corrects a coding error, you are not responsible for the denied "
                    "amount.",
                ),
                (
                    "8.3",
                    "Bundled and Same-Day Services",
                    "An office visit on the same day as a minor procedure is included in the "
                    "procedure payment, unless the provider performed a significant, separately "
                    "identifiable evaluation and reports it with modifier 25. Lab tests that are "
                    "part of a panel are paid as the panel. A network provider may not bill you for "
                    "services denied as bundled.",
                ),
                (
                    "8.4",
                    "Duplicate Claims",
                    "We deny a claim line that duplicates a service already paid. A service done on "
                    "both sides of the body, or more than once on the same day, is not a duplicate "
                    "when it is billed with the right modifier (such as 50, RT/LT or 59).",
                ),
                (
                    "8.5",
                    "Corrected Claims",
                    "A provider may submit a corrected claim within 180 days of the original denial. "
                    "You may also appeal a coding denial yourself under Section 10.",
                ),
            ],
        ),
        (
            "9",
            "Exclusions",
            [
                (
                    "9.1",
                    "General Exclusions",
                    "We do not cover: cosmetic services (except reduction mammaplasty that meets "
                    "Section 5.2(c)); experimental or investigational services (Section 5.4); "
                    "services not medically necessary; services received before coverage began or "
                    "after it ended; and services for which you have no legal obligation to pay.",
                ),
            ],
        ),
        (
            "10",
            "Appeals",
            [
                (
                    "10.1",
                    "Your Right to Appeal",
                    "You, or someone you authorize, may appeal any adverse benefit determination. "
                    "A different reviewer from the one who made the original decision reviews your "
                    "appeal.",
                ),
                ("10.2", "Deadline to File an Internal Appeal", deadline_text),
                (
                    "10.3",
                    "What to Include With Your Appeal",
                    "Every appeal should include the claim number and a copy of the denial notice. "
                    "Depending on the reason for the denial, also include:\n\n"
                    f"{req_lines}{req_notes}\n\n"
                    "Also include any document the denial notice says was missing.",
                ),
                (
                    "10.4",
                    "Expedited Appeals",
                    "If waiting for a standard appeal could seriously harm your health, ask for an "
                    "expedited appeal. We decide expedited appeals within 72 hours.",
                ),
                (
                    "10.5",
                    "External Review",
                    "If we uphold our decision, you may ask for an independent external review "
                    "within four months after the final internal appeal decision.",
                ),
                (
                    "10.6",
                    "Where to Send Your Appeal",
                    f"Mail: {INSURER} Appeals Unit, {INSURER_ADDRESS}. You may also submit an "
                    f"appeal through the member portal or by calling {INSURER_PHONE}.",
                ),
            ],
        ),
    ]


# Chapters printed on each page of the plan document.
PAGES: list[list[str]] = [["1"], ["2"], ["3"], ["4"], ["5"], ["6"], ["7"], ["8"], ["9", "10"]]


def render_plan(p: Plan) -> str:
    """Render a plan as Markdown with page markers and numbered ### sections."""
    chapters = {num: (title, secs) for num, title, secs in _sections(p)}
    out = [f"# {p.name}\n\n**Evidence of Coverage, {PLAN_YEAR} plan year**  \n{INSURER}\n"]
    for page_no, chapter_nums in enumerate(PAGES, start=1):
        out.append(f"<!-- page {page_no} -->\n")
        for num in chapter_nums:
            title, secs = chapters[num]
            out.append(f"## {num}. {title}\n")
            for sec_num, sec_title, body in secs:
                out.append(f"### {sec_num} {sec_title}\n\n{body}\n")
    return "\n".join(out)


def section_numbers(p: Plan) -> set[str]:
    return {sec[0] for _, _, secs in _sections(p) for sec in secs}
