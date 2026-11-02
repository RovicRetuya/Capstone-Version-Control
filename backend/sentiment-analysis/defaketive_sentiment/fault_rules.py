"""Rules f11 (faulty) and s2 (safety), 18 Oct 2026.

Candidates C and D of research/PREREGISTRATION_round19.md, written from the
served checker's misses on the training rounds and checked part by part over
every labelled training sentence (research/check_round19_rules.py).

Rules f11 add "faulty" to a sentence the checker left unflagged:

    slow_charge   slow charging, which the team's ruling of 7 Oct counts as
                  faulty (guide Rule 9): "not fast charging", "hindi sya fast
                  charger", "It is not 65W", "matagal mag full charge"
    drain         a battery that drains fast: "mabilis malowbat", "drains
                  rapidly", "Will not last an hour"
    fiddle        working only when moved: "kailangan pitikin muna bago
                  gumana", "Always needs to be plugged and unplugged"
    not_working   forms of "not working" the word list misses: "the unit I
                  received isn't working", "won't even turn on", "di na
                  mabuhay"
    hum           a "grounded" hum in the sound, which the owner's decision
                  makes faulty (below): "grounded and humming"

Tried and not kept: "15W lang" (a fan's low power, praised as often as
complained of), "normal charging", a hang or freeze, heat read as faulty
wherever safety is flagged (29 right, 30 wrong: the safety flag was wrong
first), and two removals: a missing part (11 right, 30 wrong) and a dented box
(10 right, 13 wrong).

Rules s2 remove "safety" from a "grounded" hum, the owner's decision of 18 Oct
2026 (guide 1.6, Rule 11): "grounded" said of the sound ("grounded yung
sound", "Medyo grounded ung volume nya", "grounded and humming"), with no
shock, heat or smoke. A bare "grounded" or a shock stays safety, as the team
labelled it.

F11_OFF names f11 parts switched off, for the part-by-part check only.
"""

import re

F11_REVISION = "f11"
# f12 (2 Nov 2026) adds the "part" group below to f11: a named part that is stuck, loose, damaged or dead, and "no sound".
F12_REVISION = "f12"
S2_REVISION = "s2"
F11_OFF: set[str] = set()

_NEG = r"(?:not|hindi|hinde|hnde|hind|di|d|nd|hnd|ndi|nde|isn'?t|is\s+not|wasn'?t|doesn'?t|does\s+not|no)"
_SOFT = (
    r"(?:(?:sya|siya|cia|xa|cya|po|naman|nman|nmn|nmm|talaga|tlga|totoo|totoong|tunay|truly|truely|really|actually|even|a|an|"
    r"the|na|pa|legit|so|that|ito|to|yan|it|is|ang|siyang|syang|ganun|ganon|gaano|super|real|as)\s+)"
)
_FAST = r"(?:fast|super|turbo|quick|pass|rapid|flash)\s*-?\s*(?:charg\w*|changer|charge)"
_WATTS = r"\d{2,3}\s*(?:w|watts?)(?!\w)"
FAST_NOT_CHARGING = re.compile(r"fast\s+(?:delivery|shipping|ship\w*|deliver\w*|response|reply|transaction|dating|dumating)", re.I)
F11_PARTS = {
    "slow_charge": (
        re.compile(rf"(?<!\w){_NEG}\s+{_SOFT}{{0,3}}{_FAST}", re.I),
        re.compile(
            r"(?<!\w)(?:slow(?:ly)?|mabagal|mabagl|bagal)\s+(?:(?:mag|ma|sya|siya|po|na|ng|ang|talaga)\s+)*"
            r"(?:charg\w*|charge|mag\s*charge|pag\s*charge)",
            re.I,
        ),
        re.compile(
            r"(?<!\w)(?:charg\w*|pag\s*charge|mag\s*charge)\s+(?:(?:is|was|speed|time|sya|siya|po|na|ang)\s+)*"
            r"(?:(?:very|so|super|too|sobrang|napaka|ang)\s+)?(?:slow|mabagal|matagal|tagal)(?!\w)",
            re.I,
        ),
        re.compile(
            r"(?<!\w)(?:matagal|napakatagal|ang\s+tagal|sobrang\s+tagal|tagal)\s+(?:(?:mag|ma|maka|bago|sya|siya|po|na|ang|i|ng)\s*-?\s*)*"
            r"(?:charge|charg\w*|full|fullcharge|mapuno|magfull)",
            re.I,
        ),
        re.compile(rf"(?<!\w){_NEG}\s+{_SOFT}{{0,3}}{_WATTS}", re.I),
        re.compile(rf"(?<!\w)(?:fake|peke|pekeng)\s+(?:{_FAST}|{_WATTS})", re.I),
    ),
    "drain": (
        re.compile(
            r"(?<!\w)(?<!di\s)(?<!hindi\s)(?<!not\s)(?<!hinde\s)(?:mabilis|bilis|madali|madaling|easily|quickly|fast)\s+"
            r"(?:(?:lang|lng|din|rin|po|sya|siya|naman|nman|ma|mag|na|talaga)\s+)*(?:ma\s*-?\s*)?"
            r"(?:low\s*bat\w*|lowbat\w*|lobat\w*|drain\w*|madrain|maubos|ma\s*low\s*bat\w*|malowbat\w*|malobat\w*|ma\s*lobat\w*)",
            re.I,
        ),
        re.compile(
            r"(?<!\w)(?:drains?|drained|draining|runs?\s+out\s+of\s+(?:power|battery|charge))\s+(?:very\s+|so\s+|too\s+)?"
            r"(?:fast|quickly|rapidly|easily)",
            re.I,
        ),
        re.compile(r"(?<!\w)(?:not|isn'?t|is\s+not|hindi|di)\s+(?:(?:a|that|so|very|really)\s+)?long[\s-]*lasting\s+(?:battery|batt)", re.I),
        re.compile(
            r"(?<!\w)(?:won'?t|will\s+not|doesn'?t|does\s+not|didn'?t|did\s+not|not\s+even|di\s+pa\s+nag|hindi\s+pa\s+nag|di\s+umabot\s+ng)\s+"
            r"(?:last\s+)?(?:an|1|one|isang)\s+(?:hour|hr|oras)",
            re.I,
        ),
        re.compile(r"(?<!\w)less\s+than\s+(?:an|1|one)\s+(?:hour|hr)", re.I),
    ),
    "fiddle": (
        re.compile(
            r"(?<!\w)(?:kailangan|need\s+to|needs\s+to|have\s+to|has\s+to|kelangan|kelngan|dapat)\s+"
            r"(?:(?:pa|ko|mo|munang|muna|be|constantly|always|lagi|i|na)\s*-?\s*){0,3}"
            r"(?:alis\w*|tanggal\w*|galaw\w*|igalaw\w*|pitik\w*|move\w*|moved|shake|unplug\w*|plug\w*|remov\w*|wiggl\w*|reconnect\w*|"
            r"tap\w*|ipitik|tapikin|alugin)"
            r"(?:\s+[\w'-]+){0,8}?\s+(?:para|to\s+make|bago|to\s+hear|to\s+get|so\s+(?:it|that))\s+(?:[\w'-]+\s+){0,3}?"
            r"(?:gumana|work\w*|tumunog|sounds?|marinig|charg\w*|mag\s*continue|continue|mabuhay|umandar|connect\w*|record)",
            re.I,
        ),
        re.compile(
            r"(?<!\w)(?:pull\s+it\s+on\s+and\s+off|plugged\s+and\s+unplugged|alis[\s-]*balik|"
            r"(?:igalaw[\s-]*galaw|galaw[\s-]*galaw\w*)\s+(?:[\w'-]+\s+){0,3}(?:jack|wire|cord|cable|plug|saksak\w*))",
            re.I,
        ),
    ),
    "part": (
        # "broke instantly", "nasira agad": "sira agad" is already read; the English wording was not
        re.compile(r"(?<!\w)(?:broke|broken|snapped|cracked)\s+(?:right\s+away|instantly|immediately|within\s+(?:a\s+)?(?:day|days|week))", re.I),
        # 'Key "G" is stuck', "keys not responding", "button is loose", "the scroll wheel stopped"
        re.compile(
            r"(?<!\w)(?:keys?|buttons?|clicks?|analog|joystick|scroll(?:\s*wheel)?|wheel|trigger|switch|touchpad|usb\s+port|charging\s+port|port|jack|screen)(?!\w)"
            r"(?:\s+[\w'\"]+){0,4}?\s+(?:(?:is|are|was|were|keeps?|na)\s+)?"
            r"(?:not\s+responding|unresponsive|stuck|sticky|loose|jammed|stopped\s+working|(?:di|hindi)\s+(?:na\s+)?(?:gumagana|nagana|gumana|tumutugon)|ayaw\s+gumana)",
            re.I,
        ),
        # "damage po yung USB port", "sira ung charging port", "basag ang screen"
        re.compile(
            r"(?<!\w)(?<!no\s)(?<!not\s)(?<!walang\s)(?<!without\s)(?:damage[d]?|sira|basag|broken|loose|natanggal)\s+(?:po\s+)?(?:(?:yung|ung|ang|ng|the|sa)\s+)?"
            r"(?:[\w']+\s+){0,1}(?:usb\s+port|charging\s+port|port|jack|button|key|keys|screen|hinge|handle|switch|knob|wheel)(?!\w)",
            re.I,
        ),
        # a control that moves or presses by itself: "left analog kusang gumagalaw", "ghost touch"
        re.compile(r"(?<!\w)(?:kusang\s+(?:gumagalaw|umiikot|nagpipindot|nag\w+)|ghost[\s-]*(?:touch\w*|click\w*|tap\w*|press\w*)|stick\s+drift)", re.I),
        re.compile(r"(?<!\w)(?:(?:di|hindi|not)\s+(?:po\s+)?consistent|inconsistent)(?!\w)", re.I),
        # "no sound": "walang sound", "walng pong sound yong left", "wala pong tunog"
        re.compile(r"(?<!\w)wa?le?ng\s+(?:po(?:ng)?\s+)?(?:sound|tunog|audio|boses)(?!\w)", re.I),
        re.compile(r"(?<!\w)(?:no|zero)\s+sound\s+(?:on|from|in|at|sa)\s+(?:the\s+)?(?:left|right|one|isa)(?!\w)", re.I),
    ),
    "not_working": (
        re.compile(r"(?<!\w)(?:no\s+longer|isn'?t|is\s+not|wasn'?t|not)\s+(?:even\s+)?(?:working|functioning|functional|function)(?!\w)", re.I),
        re.compile(
            r"(?<!\w)(?:won'?t|will\s+not|doesn'?t|does\s+not|didn'?t|did\s+not|cannot|can'?t|wouldn'?t)\s+(?:even\s+)?"
            r"(?:turn\s+on|power\s+on|start|work|charge|function|play)(?!\w)",
            re.I,
        ),
        re.compile(
            r"(?<!\w)(?:di|hindi|hinde|hnde|ndi|nd|hnd)\s+(?:(?:na|po|sya|siya|naman|nman|man\s+lang|talaga)\s+)*"
            r"(?:mabuhay|nabubuhay|gumagana|gumana|nagana|magamit|nagamit|nagfufunction|nagchacharge|nag\s+cha?rge|tumutunog|natunog|umaandar)(?!\w)",
            re.I,
        ),
        re.compile(r"(?<!\w)(?:ayaw|ayw)\s+(?:(?:na|po|sya|siya|naman)\s+)*(?:gumana|mag\s*on|umandar|magcharge|mag\s+charge|tumunog)(?!\w)", re.I),
        re.compile(
            r"(?<!\w)(?:shuts?\s*down|shutdown|turns?\s+off|namamatay|nag\s*o?off)\s+"
            r"(?:(?:suddenly|by\s+itself|on\s+its\s+own|mag\s*isa|bigla|agad|kusa)\b)",
            re.I,
        ),
    ),
}
F11_GUARD = re.compile(
    r"(?<!\w)(?:sana|hope|hopefully|baka|wish|if|kung|pag\s+di|unless|i\s+hope|para\s+di|para\s+hindi|wag\s+sana|no\s+need|needed|"
    r"not\s+needed|doesn'?t\s+need|support\w*\s+fast|phone\s+(?:doesn'?t|does\s+not)\s+support)(?!\w)",
    re.I,
)
MISTAKEN = re.compile(r"(?<!\w)(?:akala\s+ko|kala\s+ko|i\s+thought)\s+(?:[\w']+\s+){0,3}?(?:hindi|di|not|ayaw|sira)", re.I)
STOCK = re.compile(r"(?<!\w)stocks?(?!\w)", re.I)

GROUND_TERM = re.compile(r"^(?:grounded|ground|grounding)$", re.I)
GROUNDED = re.compile(r"(?<!\w)(?:grounded|grounding)(?!\w)", re.I)
SOUND_WORDS = re.compile(
    r"(?<!\w)(?:noise|noisy|hum\w*|buzz\w*|static\w*|tunog|sounds?|boses|voice|volume|ugong|ingay|maingay|audio|"
    r"naririnig|marinig|nagsasalita|speaking|record\w*|kunat)(?!\w)",
    re.I,
)
SHOCK_OR_HEAT = re.compile(
    r"(?<!\w)(?:shock\w*|kuryente|nakuryente|kinuryente|spark\w*|init|uminit|umiinit|mainit|hot|heat\w*|usok|umusok|smok\w*|sunog|"
    r"nasunog|burn\w*|melt\w*|explod\w*|sumabog|pumutok|nakaka\s*ground\w*|nag\s*ga\s*ground\w*|nagga\s*ground\w*|touch\w*|hawak\w*|"
    r"got\s+grounded|broke|sira(?:ng)?\s+(?:pc|laptop|jack))(?!\w)",
    re.I,
)


def f11_match(raw: str) -> tuple[str, tuple[int, int]] | None:
    """The first f11 part that reports a fault in this sentence, with its span in the raw text."""
    text = str(raw)
    if F11_GUARD.search(text):
        return None
    if "hum" not in F11_OFF and SOUND_WORDS.search(text) and not SHOCK_OR_HEAT.search(text):
        found = GROUNDED.search(text)
        if found is not None:
            return "hum", found.span()
    for part, patterns in F11_PARTS.items():
        if part in F11_OFF:
            continue
        for pattern in patterns:
            found = pattern.search(text)
            if found is None:
                continue
            if part == "not_working" and MISTAKEN.search(text):
                break
            if part == "drain" and STOCK.search(text):
                break
            if part == "slow_charge" and FAST_NOT_CHARGING.search(text[found.start(): found.end() + 20]):
                continue
            return part, found.span()
    return None


def s2_removes(raw: str, safety_words: list[str]) -> bool:
    """True when every safety word is a plain "grounded", the sentence is about the sound, and nothing shocks or heats."""
    if not safety_words or not all(GROUND_TERM.match(word.strip()) for word in safety_words):
        return False
    return bool(SOUND_WORDS.search(raw)) and not SHOCK_OR_HEAT.search(raw)
