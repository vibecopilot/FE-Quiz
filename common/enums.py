from django.db import models
class Zone(models.TextChoices):
    NORTH = "NORTH", "North"
    SOUTH = "SOUTH", "South"
    EAST  = "EAST",  "East"
    WEST  = "WEST",  "West"
    CENTRAL = "CENTRAL", "Central"


class Difficulty(models.TextChoices):
    EASY = "easy", "Easy"
    MEDIUM = "medium", "Medium"
    HARD = "hard", "Hard"


class QuestionType(models.TextChoices):
    SINGLE_CHOICE = "single", "Single choice"
    MULTI_CHOICE  = "multi", "Multi choice"
    TRUE_FALSE    = "bool",  "True/False"
    TEXT          = "text",  "Short text"
    NUMBER        = "number","Number"


class AttemptStatus(models.TextChoices):
    STARTED     = "started",      "Started"
    SUBMITTED   = "submitted",    "Submitted"
    DISQUALIFIED= "disqualified", "Disqualified"
    EXPIRED     = "expired",      "Expired"


class AntiCheatCode(models.TextChoices):
    TAB_SWITCH     = "tab_switch",     "Tab/Window switch"
    FULLSCREEN_EXIT= "fullscreen_exit","Fullscreen exit"
    DEVTOOLS_OPEN  = "devtools",       "DevTools opened"
    COPY           = "copy",           "Copy"
    PASTE          = "paste",          "Paste"
    MULTI_WINDOW   = "multi_window",   "Multiple windows"
    ID_MISMATCH    = "id_mismatch",    "Identity mismatch"
    MULTI_PERSON   = "MULTI_PERSON",   "MULTI PERSON Detected"
    OTHER          = "other",          "Other"


class IndianState(models.TextChoices):
    ANDHRA_PRADESH = "ANDHRA_PRADESH", "Andhra Pradesh"
    ARUNACHAL_PRADESH = "ARUNACHAL_PRADESH", "Arunachal Pradesh"
    ASSAM = "ASSAM", "Assam"
    BIHAR = "BIHAR", "Bihar"
    CHHATTISGARH = "CHHATTISGARH", "Chhattisgarh"
    GOA = "GOA", "Goa"
    GUJARAT = "GUJARAT", "Gujarat"
    HARYANA = "HARYANA", "Haryana"
    HIMACHAL_PRADESH = "HIMACHAL_PRADESH", "Himachal Pradesh"
    JHARKHAND = "JHARKHAND", "Jharkhand"
    KARNATAKA = "KARNATAKA", "Karnataka"
    KERALA = "KERALA", "Kerala"
    MADHYA_PRADESH = "MADHYA_PRADESH", "Madhya Pradesh"
    MAHARASHTRA = "MAHARASHTRA", "Maharashtra"
    MANIPUR = "MANIPUR", "Manipur"
    MEGHALAYA = "MEGHALAYA", "Meghalaya"
    MIZORAM = "MIZORAM", "Mizoram"
    NAGALAND = "NAGALAND", "Nagaland"
    ODISHA = "ODISHA", "Odisha"
    PUNJAB = "PUNJAB", "Punjab"
    RAJASTHAN = "RAJASTHAN", "Rajasthan"
    SIKKIM = "SIKKIM", "Sikkim"
    TAMIL_NADU = "TAMIL_NADU", "Tamil Nadu"
    TELANGANA = "TELANGANA", "Telangana"
    TRIPURA = "TRIPURA", "Tripura"
    UTTAR_PRADESH = "UTTAR_PRADESH", "Uttar Pradesh"
    UTTARAKHAND = "UTTARAKHAND", "Uttarakhand"
    WEST_BENGAL = "WEST_BENGAL", "West Bengal"
    ANDAMAN_NICOBAR = "ANDAMAN_NICOBAR", "Andaman & Nicobar Islands"
    CHANDIGARH = "CHANDIGARH", "Chandigarh"
    DNH_DD = "DNH_DD", "Dadra & Nagar Haveli and Daman & Diu"
    DELHI_NCT = "DELHI_NCT", "Delhi (NCT)"
    JAMMU_KASHMIR = "JAMMU_KASHMIR", "Jammu & Kashmir"
    LADAKH = "LADAKH", "Ladakh"
    LAKSHADWEEP = "LAKSHADWEEP", "Lakshadweep"
    PUDUCHERRY = "PUDUCHERRY", "Puducherry"

