"""
Seeds a small, curated healthcare knowledge base for development and
testing. Sources are described plainly (publisher name) rather than
invented — content is paraphrased general-education material, not a
verbatim reproduction of any single source, and every document records
where the information is broadly drawn from.

This is deliberately small (per Phase 3 scope: "use a small curated
dataset rather than attempting to ingest the entire internet").
"""

from knowledge.models import HealthcareDocument

SEED_DOCUMENTS = [
    dict(
        title="What Is Blood Pressure?",
        category=HealthcareDocument.Category.GENERAL_HEALTH,
        source="MedlinePlus (U.S. National Library of Medicine)",
        source_url="https://medlineplus.gov/bloodpressure.html",
        content=(
            "Blood pressure is the force of blood pushing against the walls of your arteries as your "
            "heart pumps. It is written as two numbers: systolic pressure (the higher number, when the "
            "heart beats) over diastolic pressure (the lower number, when the heart rests between beats), "
            "measured in millimeters of mercury (mmHg). A typical healthy reading is often cited as around "
            "120/80 mmHg, though normal ranges can vary by individual and are best interpreted by a "
            "healthcare professional. Blood pressure that is consistently too high is called hypertension, "
            "and consistently too low is called hypotension. Both can have a range of causes and are usually "
            "monitored over multiple readings rather than judged from a single measurement."
        ),
    ),
    dict(
        title="Understanding Fasting Before a Blood Test",
        category=HealthcareDocument.Category.DIAGNOSTIC_TESTS,
        source="MedlinePlus (U.S. National Library of Medicine)",
        source_url="https://medlineplus.gov/labtests/fastingforalabtest.html",
        content=(
            "Some blood tests require fasting beforehand, meaning not eating or drinking anything except "
            "water for a set period — commonly 8 to 12 hours — before the sample is drawn. Fasting is "
            "typically requested for tests such as blood glucose and lipid (cholesterol) panels, because "
            "eating can temporarily raise blood sugar and fat levels, which could make results less "
            "accurate. Patients are usually told in advance whether a specific test requires fasting, and "
            "should confirm with their provider or the lab, since not every blood test needs it. Water is "
            "generally still allowed and encouraged during a fast unless a provider says otherwise."
        ),
    ),
    dict(
        title="What Happens During an X-Ray",
        category=HealthcareDocument.Category.DIAGNOSTIC_TESTS,
        source="Radiological Society of North America (RadiologyInfo.org)",
        source_url="https://www.radiologyinfo.org/en/info/genrad",
        content=(
            "An X-ray is an imaging test that uses a small amount of radiation to create pictures of the "
            "inside of the body, commonly used to look at bones, the chest, or the abdomen. During the "
            "procedure, the patient is positioned near an X-ray machine, and a technologist captures images "
            "from one or more angles. The process is quick, generally painless, and does not require "
            "sedation. Because it uses ionizing radiation, providers weigh the benefit of the images against "
            "the (typically low) radiation exposure, and may take extra precautions for pregnant patients. "
            "Results are interpreted by a radiologist and shared with the ordering provider."
        ),
    ),
    dict(
        title="What Is an MRI Scan?",
        category=HealthcareDocument.Category.DIAGNOSTIC_TESTS,
        source="Radiological Society of North America (RadiologyInfo.org)",
        source_url="https://www.radiologyinfo.org/en/info/mri-body",
        content=(
            "Magnetic resonance imaging (MRI) is an imaging test that uses a strong magnetic field and radio "
            "waves — not ionizing radiation — to produce detailed images of organs, soft tissue, and bone. "
            "It is often used when more detail is needed than an X-ray can provide, such as for the brain, "
            "spine, or joints. Patients lie inside a large cylindrical scanner, and the scan can take "
            "anywhere from 15 minutes to over an hour depending on what's being imaged. The machine is loud, "
            "so earplugs or headphones are often provided. Because it uses strong magnets, patients are "
            "screened beforehand for metal implants or devices that could be affected."
        ),
    ),
    dict(
        title="Common Causes of a Cough",
        category=HealthcareDocument.Category.SYMPTOMS,
        source="MedlinePlus (U.S. National Library of Medicine)",
        source_url="https://medlineplus.gov/cough.html",
        content=(
            "A cough is a common symptom with many possible causes, ranging from mild and self-limited (such "
            "as a cold, seasonal allergies, or irritants like smoke) to conditions that benefit from medical "
            "evaluation (such as bronchitis, pneumonia, or asthma). Coughs are often described as acute "
            "(lasting under 3 weeks), subacute (3 to 8 weeks), or chronic (over 8 weeks), and the duration "
            "can help a provider narrow down likely causes. A cough accompanied by high fever, difficulty "
            "breathing, chest pain, or coughing up blood is generally considered a reason to seek prompt "
            "medical attention rather than waiting it out."
        ),
    ),
    dict(
        title="Understanding Fever",
        category=HealthcareDocument.Category.SYMPTOMS,
        source="MedlinePlus (U.S. National Library of Medicine)",
        source_url="https://medlineplus.gov/fever.html",
        content=(
            "A fever is a temporary increase in body temperature, often caused by the body's immune response "
            "to an infection. For most adults, a temperature at or above 100.4°F (38°C) is generally "
            "considered a fever. Mild fevers are often managed at home with rest and fluids, but a fever that "
            "is very high, lasts more than a few days, or is accompanied by symptoms like a stiff neck, "
            "confusion, difficulty breathing, or a rash is generally a reason to seek medical care. Fevers "
            "can also affect infants, older adults, and people with weakened immune systems differently, and "
            "these groups are often advised to seek care sooner."
        ),
    ),
    dict(
        title="Recommended Preventive Health Screenings",
        category=HealthcareDocument.Category.PREVENTIVE_CARE,
        source="U.S. Preventive Services Task Force (USPSTF)",
        source_url="https://www.uspreventiveservicestaskforce.org/",
        content=(
            "Preventive care refers to routine checkups and screenings intended to catch potential health "
            "issues early, before symptoms appear. Common examples include blood pressure checks, "
            "cholesterol screening, cancer screenings (such as mammograms or colonoscopies, generally "
            "starting at ages recommended by a provider), vaccinations, and dental and vision checkups. "
            "Recommended screenings and their frequency vary based on age, sex, family history, and personal "
            "risk factors, so a primary care provider is generally the best source for a personalized "
            "preventive care schedule rather than a one-size-fits-all list."
        ),
    ),
    dict(
        title="What to Expect From a Routine Blood Draw",
        category=HealthcareDocument.Category.COMMON_PROCEDURES,
        source="MedlinePlus (U.S. National Library of Medicine)",
        source_url="https://medlineplus.gov/lab-tests/blood-tests/",
        content=(
            "A routine blood draw (venipuncture) involves a healthcare worker inserting a small needle into "
            "a vein, usually in the arm, to collect a blood sample for testing. The process typically takes "
            "just a few minutes. Patients may feel a brief pinch or sting during the needle insertion, and "
            "mild bruising at the site is common afterward but usually resolves quickly. Depending on the "
            "test ordered, patients may be asked to fast beforehand (see the separate fasting document). "
            "Results are typically available anywhere from same-day to a few days later, depending on the "
            "type of test and lab."
        ),
    ),
    dict(
        title="Types of Healthcare Providers and When to See Them",
        category=HealthcareDocument.Category.HEALTHCARE_SERVICES,
        source="MedlinePlus (U.S. National Library of Medicine)",
        source_url="https://medlineplus.gov/healthcheckup.html",
        content=(
            "Healthcare systems typically include several types of providers. Primary care providers (family "
            "medicine, internal medicine, or general practitioners) handle routine checkups, general health "
            "concerns, and referrals. Specialists — such as dermatologists, cardiologists, or "
            "endocrinologists — focus on a particular body system or condition and are often seen after a "
            "referral or when a specific concern arises. Urgent care centers handle non-life-threatening "
            "issues that need prompt attention, like minor injuries or infections, generally faster than a "
            "primary care appointment but without emergency-level resources. Emergency departments are "
            "reserved for potentially life-threatening conditions and are equipped to respond immediately."
        ),
    ),
    dict(
        title="Understanding Cholesterol and Lipid Panels",
        category=HealthcareDocument.Category.DIAGNOSTIC_TESTS,
        source="MedlinePlus (U.S. National Library of Medicine)",
        source_url="https://medlineplus.gov/cholesterol.html",
        content=(
            "A lipid panel is a blood test that measures cholesterol and triglyceride levels, typically "
            "broken down into total cholesterol, LDL ('bad') cholesterol, HDL ('good') cholesterol, and "
            "triglycerides. It's commonly used to assess cardiovascular risk. This test is one of the ones "
            "that often requires fasting beforehand, since eating can temporarily raise triglyceride levels. "
            "Results are interpreted in the context of a person's overall health, family history, and other "
            "risk factors by a healthcare provider, rather than judged from the numbers alone."
        ),
    ),
]


def get_seed_documents() -> list[dict]:
    return list(SEED_DOCUMENTS)
