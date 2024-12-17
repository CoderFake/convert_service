from dataclasses import dataclass, field
from typing import Optional, ClassVar, Dict

@dataclass
class PatientRecord:
    COLUMN_NAMES: ClassVar[Dict[str, str]] = {
        "agency_name": "代行業者名",
        "patient_name_kana": "受診者カナ",
        "gender": "性別",
        "date_of_birth": "生年月日",
        "postal_code": "郵便番号",
        "course_name": "受診コース名",
        "course_code": "コースコード",
        "desired_booking_date": "予約希望日"
    }

    agency_name: str
    patient_name_kana: str
    gender: str
    date_of_birth: str
    postal_code: str
    course_name: str
    course_code: Optional[str] = field(default="")
    desired_booking_date: Optional[str] = field(default="")
