from services.medical_dictionary import MEDICAL_TERMS


def explain_medical_terms(text):
    explanations = {}

    for term, explanation in MEDICAL_TERMS.items():
        if term in text:
            explanations[term] = explanation

    return explanations