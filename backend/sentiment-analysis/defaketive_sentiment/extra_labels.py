"""Rules for the two labels added in tagging guide 1.4.

  quality           the product works, but poorly; feels cheap or flimsy; or
                    arrived dented, scratched or torn
  not_as_described  a size, capacity, feature or look differs from what the
                    listing says or shows

They sit beside the three badge categories (safety, defect, counterfeit) and
never change them. Everything here works on normalized text
(`text_norm.normalize_with_spans`), where "nasira" is already "sira" and
"charging" is "charge".

First written from labelling rounds 5-6 and revised on rounds 1-6
(research/RESULTS_TABLES.md, Tables 11i-11j). Round 7 was kept out of the
revision so there is one round the patterns were not fitted to.

Tagging guide 1.5 (16 Oct 2026) defines both labels in full; revision r5
below follows it and is what the checker serves under keyword rules 0.4
(held-out round 13, research/RESULTS_TABLES.md, Table 12i).
"""

from __future__ import annotations

import re

QUALITY = "quality"
NOT_AS_DESCRIBED = "not_as_described"
EXTRA_TAGS = (QUALITY, NOT_AS_DESCRIBED)
# Part of the checker's version string, so saved reports are redone when the
# patterns change. r2 = the second revision of 8 Oct 2026, which changed the
# poor-quality patterns. A revision of the not-as-advertised patterns was
# written at the same time and dropped: on held-out sentences it found nothing
# new (research/label_rules_revision.json).
EXTRA_RULES_REVISION = "r2"

_NOT = r"(?:hindi|hinde|di|d|nd|ndi|not|isn't|isnt|wasn't|wasnt|ain't|aint|doesn't|doesnt|never)"
# The poor-quality patterns also read three common misspellings of "hindi".
_NOT_WIDE = r"(?:hindi|hinde|hind|hndi|hnd|di|d|nd|ndi|not|isn't|isnt|wasn't|wasnt|ain't|aint|doesn't|doesnt|never)"
_FILL = r"(?:[\w']+\s+)"
_NUM = r"\d[\d,.]*"
_UNIT = r"(?:k\s*)?(?:mah|gb|tb|mbps|watts?|w|meters?|mtrs?|m|cm|liters?|litter|l|ml|inch(?:es)?|ribs)"
_SHOWN = r"(?:pictures?|pics?|photos?|litrato|display|description|discription|thumbnail|ads?|post)"
_SOFT = r"(?:(?:po|naman|nman|talaga|tlga|sya|siya|cya|xa|sia|rin|din|a|even|really|totally)\s+)"
_DEGREE = r"(?:(?:sya|siya|xa|cya|sia|sha|po|kc|kasi|ganun|ganoon|ganon|gaano|gaanong|ganung|masyado|masyadong|that|so|very|naman|talaga|look|looks)\s+)"


def _compile(patterns: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(rf"(?<!\w)(?:{pattern})", re.IGNORECASE) for pattern in patterns)


NOT_AS_DESCRIBED_PATTERNS = _compile(
    (
        # "Fake ung 20000mah", "peke ung nakalagay na 10400mah"
        rf"(?:fake|peke)\s+{_FILL}{{0,3}}{_NUM}\s*{_UNIT}(?!\w)",
        # "hindi legit na 20k mah", "not even 2 liter", "hindi rin saktong 5m", "hindi totoong 10 meters"
        rf"{_NOT}\s+{_FILL}{{0,2}}(?:legit|totoo|totoong|true|accurate|originally|saktong|even)\s+{_FILL}{{0,3}}{_NUM}",
        # "hindi sya 10meters", "d sya totally 512gb"
        rf"{_NOT}\s+{_SOFT}{{0,3}}{_NUM}\s*{_UNIT}(?!\w)",
        # "only 30cm", "i received just 22.5w"
        rf"(?:only|just)\s+{_NUM}\s*{_UNIT}(?!\w)",
        # "sabi 10 meters", "nakalagay 30m", "nasa description niyo 2l", "akala ko ba 10meter", "65w daw"
        rf"(?:sabi|nakalagay|naka lagay|naka post|nakapost|description|discription|stated|advertised|akala ko|kala ko|akala q)\s+{_FILL}{{0,3}}{_NUM}\s*{_UNIT}(?!\w)",
        rf"{_NUM}\s*{_UNIT}\s+daw(?!\w)",
        rf"instead (?:of |a )?{_NUM}\s*{_UNIT}(?!\w)",
        r"(?:misleading|nakaka ?misleading|nakakamisleading|false advertis\w*|fake (?:description|ads?|advertisement|specs?)"
        r"|wrong (?:description|discription|specs?)|expectation vs\.? reality|not what you see)(?!\w)",
        r"(?:hindi|hinde|di|nd|ndi)\s+(?:po\s+|naman\s+|nga\s+)?(?:totoo|totoong)(?!\w)",
        # "not the same as described", "different from what is advertised", "lighter than advertised"
        rf"(?:not|hindi|di)\s+{_FILL}{{0,4}}(?:as|sa)\s+(?:described|advertised|stated)(?!\w)",
        r"(?:than|from what is|kesa sa|kaysa sa|sa)\s+(?:advertised|stated|described)(?!\w)",
        r"not (?:the )?same (?:as |with |sa |in )?(?:the |sa )?(?:description|described|pictures?|pics?|photos?|ads?)(?!\w)",
        r"different from (?:what is |the )?(?:advertised|description|pictures?)(?!\w)",
        r"kulang (?:sa|ang|yung|ung|ng)\s+(?:sukat|measurement|haba)(?!\w)",
        rf"{_NOT}\s+{_SOFT}{{0,2}}accurate\s+{_FILL}{{0,2}}(?:sizes?|sukat|measurement|medium|large)(?!\w)",
        rf"(?:sizes?|sukat|measurement)\s+{_FILL}{{0,3}}{_NOT}\s+{_SOFT}{{0,2}}accurate(?!\w)",
        # "hindi naman fast charge" (normalized "charging"), "not waterproof", "hindi photochromic"
        rf"{_NOT}\s+{_SOFT}{{0,3}}(?:fast charge\w*|fastcharg\w*|water ?proof|photochromic|smudge ?proof|true to size|5g|sensor)(?!\w)",
        # "ibang iba sa picture", "ang layo ng kulay sa picture", "malayo yung shade kesa sa nasa pic"
        rf"(?:ibang ibang?|iba|ibang|malayo|anlayo|layo|layu)\s+{_FILL}{{0,5}}(?:kesa sa|kaysa sa|sa)\s+{_FILL}{{0,2}}{_SHOWN}(?!\w)",
        # "hindi katulad nung nasa picture", "looks nothing like in the picture"
        rf"{_NOT}\s+{_FILL}{{0,3}}(?:tulad|katulad|gaya|kagaya|pareho|kapareho|same|like)\s+{_FILL}{{0,4}}{_SHOWN}(?!\w)",
        rf"nothing like\s+{_FILL}{{0,2}}{_SHOWN}(?!\w)",
        # "hindi naman ganyan yung kulay at design na nasa picture"
        rf"{_NOT}\s+{_FILL}{{0,2}}(?:ganyan|ganito|ganun|ganoon)\s+{_FILL}{{0,6}}{_SHOWN}(?!\w)",
        # "sa picture lang maganda", "maganda lng sya sa pic"
        rf"sa\s+{_SHOWN}\s+(?:lang|lng)\s+(?:naman\s+)?(?:maganda|ganda)(?!\w)",
        rf"(?:maganda|ganda)\s+{_FILL}{{0,2}}(?:lang|lng)\s+{_FILL}{{0,2}}sa\s+{_SHOWN}(?!\w)",
        rf"{_SHOWN}\s+{_FILL}{{0,5}}(?:is|are)\s+different(?!\w)",
        rf"different\s+{_FILL}{{0,4}}(?:on|in|sa|from)\s+{_FILL}{{0,2}}{_SHOWN}(?!\w)",
    )
)
# "N unit lang" needs two guards, so it is kept apart: the number is often the
# reviewer's own phone ("3500mah lang battery ng cp ko").
# Litres are left out: "1l lang ang dumating" is nearly always a wrong variant sent.
_SPEC_UNIT = r"(?:k\s*)?(?:mah|gb|tb|mbps|watts?|w|meters?|mtrs?|m|cm|inch(?:es)?|ribs)"
ONLY_NUMBER = re.compile(rf"(?<!\w){_NUM}\s*{_SPEC_UNIT}\s+(?:lang|lng|only)(?!\w)", re.IGNORECASE)
OWN_DEVICE_AFTER = re.compile(
    r"\s*(?:[\w']+\s+){0,4}(?:cp|phone|cellphone|battery ng|samsung|iphone|oppo|vivo|realme|capacity nitong|sana)(?!\w)",
    re.IGNORECASE,
)
# "yung isa kong gamit 20W lang": the reviewer's other or older device, named
# before the number (seen on a whole listing, 8 Oct 2026; no labelled round
# has a report that this guard removes).
OWN_DEVICE_BEFORE = re.compile(
    r"(?<!\w)(?:(?:yung|ung|ang|my)\s+(?:isa|luma|dati|other|old)|(?:isa|luma|dati|gamit)\s+ko(?:ng)?)\s+(?:[\w']+\s+){0,3}$",
    re.IGNORECASE,
)
CONCESSION_BEFORE = re.compile(r"(?<!\w)(?:kahit|may|pang)\s+$", re.IGNORECASE)
# "mas light compared dun sa picture" is a report; "mas maganda kesa sa picture" is praise.
COMPARED_TO_SHOWN = re.compile(rf"(?<!\w)(?:compared?|kumpara|kesa|kaysa)\s+{_FILL}{{0,3}}{_SHOWN}(?!\w)", re.IGNORECASE)
PRAISE_BEFORE = re.compile(r"(?<!\w)(?:mas\s+)?(?:maganda|ganda|okay|ok|better|nice)\s+(?:[\w']+\s+){0,3}$", re.IGNORECASE)
SPECULATION = re.compile(r"(?<!\w)(?:baka|bka|maybe|might)\s+(?:[\w']+\s+){0,2}$", re.IGNORECASE)

QUALITY_PATTERNS = _compile(
    (
        # weak
        r"(?:(?:ma|napaka)?hina|mahinang)(?!\w)",
        rf"{_NOT_WIDE}\s+{_DEGREE}{{0,2}}(?:ka)?(?:lakas|malakas|kalakasan|loud)(?!\w)",
        r"(?:volume too low|mas tumutunog pa)(?!\w)",
        rf"mas malakas pa\s+{_FILL}{{0,5}}(?:kesa|kaysa)(?!\w)",
        r"mas malakas pa (?:ang )?(?:ihip|hininga)(?!\w)",
        # sound
        rf"sabog\s+{_FILL}{{0,2}}(?:tunog|sounds?|speaker|mic|microphone)(?!\w)",
        rf"(?:tunog|sounds?|speaker|mic|microphone)\s+{_FILL}{{0,3}}sabog(?!\w)",
        rf"basag\s+{_FILL}{{0,2}}(?:tunog|sounds?|music|pakinggan)(?!\w)",
        rf"(?:tunog|sounds?)\s+{_FILL}{{0,2}}basag(?!\w)",
        r"(?:sabog sya|tunog lata|wasak sound|maugong|garalgal|not enough bass|bass is meh)(?!\w)",
        rf"(?:pangit|panget)\s+{_FILL}{{0,2}}(?:tunog|sounds?|boses)(?!\w)",
        rf"{_NOT_WIDE}\s+{_FILL}{{0,2}}(?:maganda|kaganda|ganda)\s+{_FILL}{{0,3}}(?:tunog|sounds?)(?!\w)",
        # quality words
        r"(?:low|poor|bad|cheap|awful) (?:sound |build |product )?quality(?!\w)",
        r"quality\s*:?\s*(?:is |was |nya |niya |ng \w+ )?(?:not good|awful|bad|poor|pangit|panget|low)(?!\w)",
        rf"(?:pangit|panget|baba|bulok)\s+{_FILL}{{0,2}}quality(?!\w)",
        rf"{_NOT_WIDE}\s+{_FILL}{{0,2}}(?:maganda|ganda|kaganda|good|high)\s+{_FILL}{{0,3}}quality(?!\w)",
        r"(?:low class|poor product|poor performance|poor performace|cheap plastic|mumurahin|substandard|cheaply made"
        r"|cheap material|flimsy|meh lang)(?!\w)",
        r"functionality\s*:?\s*(?:poor|pangit|panget)(?!\w)",
        # thin, fragile, toy-like
        r"(?:ma|ka|napaka)?nipis\w*",
        r"marupok(?!\w)",
        r"(?:madali|madaling|mabilis|dali|bilis)\s+(?:(?:lang|lng|na|ma|sya|siya|nya|nga)\s+){0,2}"
        r"(?:sira|masira|mapunit|punit|maputol|putol|matanggal|tanggal|mabura|mawala|kumupas|lumuwag|maluwag)(?!\w)",
        rf"{_NOT_WIDE}\s+{_DEGREE}{{0,3}}(?:ka)?(?:tibay|matibay|sturdy|durable|stable)(?!\w)",
        r"(?:parang|para siyang|para syang|para lang|mukhang|mukang)\s+(?:laruan|laroan)(?!\w)",
        # does not hold or fit
        r"(?:nahuhulog|nalalaglag|lumalaylay|wobbly|super loose|sobrang luwag)(?!\w)",
        rf"(?:maluwag|maluwang|loose)\s+{_FILL}{{0,3}}(?:turnilyo|screws?|pagkakabit|rj45|saksak\w*|plug)(?!\w)",
        rf"(?:turnilyo|screws?|saksak\w*|plug)\s+{_FILL}{{0,3}}(?:maluwag|maluwang|loose)(?!\w)",
        rf"{_NOT_WIDE}\s+{_DEGREE}{{0,2}}(?:madikit|dumidikit|nakadikit|mahigpit|pantay|pare pareho|pareho|parehas|straight)(?!\w)",
        r"(?:hindi|hinde|di|d|nd|ndi)\s+(?:(?:rin|din|po|p|masyadong)\s+){0,2}maayos\s+(?:(?:ang|yung|ung)\s+)?"
        r"(?:tahi|pagka ?tahi|pagkakabit|pagkakadikit|pgkakadikit)(?!\w)",
        # does not last (scent, colour)
        rf"(?:not long lasting|{_NOT_WIDE}\s+(?:(?:sya|siya|naman)\s+)?(?:long lasting|naglalast|nagtatagal))(?!\w)",
        # Second revision (8 Oct 2026): written from two thirds of the labelled
        # sentences and checked on the third (research/improve_label_rules.py).
        # noisy
        r"(?:maingay|ang ingay|sobrang ingay|napaka ?ingay)(?!\w)",
        # lag in sound or response
        rf"delay(?:ed)?\s+{_FILL}{{0,2}}(?:mic|sound|tunog|audio|response|pagsulat)(?!\w)",
        rf"(?:mic|sound|tunog|audio|feature)\s+{_FILL}{{0,2}}delay(?:ed)?(?!\w)",
        # "material not that expected". "The item is not good" is left out: on the
        # sentences read it was as often a fault as poor quality.
        r"(?:material|materials)\s+(?:is |was |are )?not\s+(?:very |so |that |really )?(?:good|great|expected)(?!\w)",
        # "panget gamitin", "pangit ang pagkakagawa"
        rf"(?:pangit|panget)\s+{_FILL}{{0,2}}(?:gamitin|pagkakagawa|pagkagawa|gawa|materials?|tela|tahi|print|stiker|sticker)(?!\w)",
        r"(?:napaka ?low|pucho pucho|puchu puchu)\s+quality(?!\w)",
        # "palpak ang power bank ninyo". "Bulok ang item" is left out: usually said of something broken.
        rf"palpak\s+{_FILL}{{0,2}}(?:item|product|power ?bank|unit|gawa|binigay)(?!\w)",
        # looks used
        r"(?:parang|mukhang|mukang)\s+(?:gamit na|ginamit|luma|second ?hand|used)(?!\w)",
        r"(?:not brand new|second ?hand)(?!\w)",
        # "medyo basag sya"
        r"(?:medyo|mejo|medjo)\s+basag(?!\w)",
        r"mas malakas pa\s+(?:ang\s+)?(?:sound|tunog|volume|speaker)\s+ng\s+(?:cp|phone|cellphone)(?!\w)",
        # stiff or hard to use
        r"(?:sobrang|masyadong|napaka)\s*tigas(?!\w)",
        r"hard (?:to )?press(?!\w)",
        r"hirap\s+(?:pa\s+)?(?:pindutin|buksan|hilahin|isaksak|ikabit|i ?connect|iapply)(?!\w)",
        r"(?:wonky|difficult to connect)(?!\w)",
        # too light, all plastic
        r"masyado(?:ng)?\s+magaan(?!\w)",
        r"(?:super|puro)\s+(?:fake\s+)?plastic(?!\w)",
        # cannot carry the weight
        rf"{_NOT_WIDE}\s+(?:nya\s+|niya\s+)?(?:kinakaya|kaya)\s+(?:yung|ung|ang)\s+bigat(?!\w)",
        r"malabo\s+(?:ang\s+|yung\s+|ung\s+)?(?:print|screen|camera|video|tunog|sound|mic)(?!\w)",
        r"expected ko\s+(?:makapal|matibay|malakas)(?!\w)",
    )
)
# Damage that leaves the product usable. Counted only when it is on the
# product, not on the box.
COSMETIC = re.compile(
    r"(?<!\w)(?:may (?:konti(?:ng)?|kunti(?:ng)?|maliit na) (?:basag|sira|damage|tama|crack)|dents?|dented|gasgas|scratch(?:es|ed)?|yupi|nayupi|may (?:mga )?butas|punit|tastas|cracks?|cracked|tuklap"
    r"|ukab|kalawang|tabingi|baliko|stains?|mantsa|dirty|dusty|madumi|marumi|kupas|nakaangat|umangat|nakabuka|meron(?:g)? butas)(?!\w)",
    re.IGNORECASE,
)
PACKAGING = frozenset(
    {"box", "boxes", "kahon", "karton", "package", "packaging", "packing", "parcel", "balot", "pagkakabalot",
     "wrapper", "wrapping", "pouch", "plastic", "bubble"}
)
# The shared negation test does not see through "wala pong gasgas"; the two
# new labels use this wider one.
NEGATED_BEFORE = re.compile(
    r"(?<!\w)(?:wala|walang|hindi|hinde|di|d|nd|ndi|no|not|without|zero|never|doesn'?t|does\s+not|didn'?t|did\s+not|hasn'?t|won'?t|isn'?t)\s+"
    r"(?:(?:po|pong|naman|namn|nman|namang|ng|man|talaga|any|kahit|ka|ko|sya|siya|masyado|masyadong|ganun|gaano"
    r"|gaanong|yung|ung|tipong|scratches|dents?|gasgas|or|o|at"
    r"|agad|madali|madaling|basta|bastabasta|basta-basta|mag|nag|easily|ever|will|would|get|gets|so|that|very|really)\s+){0,4}$",
    re.IGNORECASE,
)
# "tunog h di basag": a negator inside the matched words.
NEGATED_INSIDE = re.compile(
    r"(?<!\w)(?:hindi|hinde|di|d|nd|ndi|not|wala|walang)\s+(?:naman\s+|po\s+)?(?:basag|sabog|mahina|hina|manipis|nipis)(?!\w)",
    re.IGNORECASE,
)
# "may nababasa ako sa comments na mabilis nasira": someone else's report.
# "scratch resistant", "anti-scratch", "protects against cracks": praise for protection, not damage.
PROTECTIVE_BEFORE = re.compile(
    r"(?<!\w)(?:anti[\s-]*|(?:protects?|prevents?|protection)\s+(?:you\s+)?(?:from|against)\s+(?:\w+\s+)?"
    r"|para\s+(?:hindi|di|walang)\s+(?:\w+\s+){0,2}(?:mag\s*)?)$",
    re.IGNORECASE,
)
PROTECTIVE_AFTER = re.compile(r"^[\s-]*(?:resistant|resistance|proof|free)(?!\w)", re.IGNORECASE)
HEARSAY_BEFORE = re.compile(
    r"(?<!\w)(?:nababasa|nabasa|comments|reviews|sabi nila|sabi ng iba)\s+(?:[\w']+\s+){0,5}$", re.IGNORECASE
)


# Revision r4 (16 Oct 2026; poor quality only, served under keyword rules 0.4,
# so r2 still reproduces for the earlier measurements). Written from the
# mistakes the adopted checker made on held-out round 10 after its single use,
# checked on every labelled round (research/check_round12_fixes.py), and
# adopted after one test on held-out round 12 (research/round12_test.json:
# weighted F1 0.368 -> 0.380, precision 0.681 -> 0.773). ("r3" was a draft
# revision of 8 Oct, dropped: research/rule_revision_3/.)
#
# Not kept: wider not-as-advertised patterns for a disputed charging speed
# ("nde nman xa fast charging", "hindi past charging", "charging still isn't
# fast", "advertised as fast charging"). 12 right and 1 wrong on the labelled
# rounds, but on round 12 they changed no sentence (F1 0.391 both), so by the
# pre-registered rule the served patterns stay.
EXTRA_RULES_REVISION_04 = "r4"
# "mabilis masira" (it broke soon) is a fault, the team's own answer on rounds
# 1-3; only "mukhang madaling masira" (it looks like it would) is poor quality.
_BREAKS_EASILY = next(pattern for pattern in QUALITY_PATTERNS if "mapunit" in pattern.pattern)
QUALITY_PATTERNS_04 = tuple(pattern for pattern in QUALITY_PATTERNS if pattern is not _BREAKS_EASILY) + _compile(
    (
        r"(?:mukhang?|mukang|mukha|parang|halatang?|feel ko|i think|looks? like|seems?)\s+(?:[\w']+\s+){0,3}"
        r"(?:madali|madaling|mabilis|dali|bilis)\s+(?:(?:lang|lng|na|ma|sya|siya|nya|nga)\s+){0,2}(?:sira|masira)(?!\w)",
        r"(?:madali|madaling|mabilis|dali|bilis)\s+(?:(?:lang|lng|na|ma|sya|siya|nya|nga)\s+){0,2}"
        r"(?:mapunit|punit|maputol|putol|matanggal|tanggal|mabura|mawala|kumupas|lumuwag|maluwag)(?!\w)",
        # the review template's own fields: "Sound Quality:It sucks", "sound is very weak"
        r"(?:sound|tunog|audio)\s*(?:quality)?\s*:?\s*(?:is\s+|was\s+)?(?:it\s+)?(?:sucks|super poor|so low|very low|too low|low|bad|meh|not good)(?!\w)",
        r"(?:the\s+)?sound\s+(?:is|was)\s+(?:so|very|too)\s+(?:low|soft|weak)(?!\w)",
        r"plastic(?:k)?y(?:\s+build)?(?!\w)",
        # a watch that counts steps or heart rate wrongly
        r"(?:steps?|heart ?rate|bpm|sensor|tracking)\s+(?:[\w']+\s+){0,3}(?:not|aren't|arent|isn't|isnt|doesn't|doesnt|hindi|di)\s+"
        r"(?:[\w']+\s+){0,2}(?:accurate|sync)\w*",
        r"(?:not|hindi|di|d)\s+(?:[\w']+\s+){0,2}accurate\s+(?:[\w']+\s+){0,8}(?:steps?|heart ?rate|bpm)(?!\w)",
    )
)
# "Material:doesn't look flimsy"
NEGATED_BEFORE_04 = re.compile(
    NEGATED_BEFORE.pattern.replace(
        r"(?:wala|walang|hindi|hinde|di|d|nd|ndi|no|not|without|zero|never)\s+",
        r"(?:wala|walang|hindi|hinde|di|d|nd|ndi|no|not|without|zero|never|doesn't|doesnt|don't|dont|isn't|isnt)\s+"
        r"(?:look\s+|looks\s+|seem\s+|feel\s+)?",
    ),
    re.IGNORECASE,
)


# Revision r5 (16 Oct 2026): both labels, written from the definitions of
# tagging guide 1.5 (Rule 10, approved by the owner that day) after rounds 1-12
# were re-checked against them (research/recheck_guide15.py). Each group is
# checked on and off over every labelled sentence
# (research/check_guide15_rules.py) and judged once on held-out round 13
# (research/PREREGISTRATION_round13.md). R5_OFF names groups switched off, for
# that check only.
EXTRA_RULES_REVISION_05 = "r5"
_NOT_05 = r"(?:hindi|hinde|hind|hndi|hnd|di|d|nd|nde|ndi|not|isn't|isnt|wasn't|wasnt|ain't|aint|doesn't|doesnt|never)"
_SOFT_05 = (
    r"(?:(?:po|naman|nman|nmn|namn|talaga|tlga|tlaga|sya|siya|cya|xa|sia|rin|din|a|an|even|really|totally|tunay|totoo"
    r"|totoong|n|na|ata|nga|ito|to|tong|yan|yung|ung|super|ultra|ganun|ganon|gaanong|that|the)\s+)"
)
_FAST_05 = r"(?:fast|past|super ?fast|ultra ?fast|turbo|quick|rapid)\s*(?:charge\w*|charger\w*|charging)"
_BODY = r"(?:tenga|tainga|ulo|kamay|wrist|leeg|balat|daliri|ears?|head|hands?|fingers?|neck|skin)"
# Words a product is sold by: a reviewer who denies one is answering the listing.
_SOLD_AS = (
    r"(?:mini|slim|ultra ?thin|wireless|mechanical|backlit|backlight|bluetooth|rechargeable|magnetic|magsafe|portable"
    r"|lightweight|silent|noise ?cancel\w*|anc|enc|stereo|hd|full ?hd|4k|touch ?screen|heavy ?duty|qwerty|genuine leather"
    r"|leather|cotton|metal|aluminum|aluminium|water ?resistant|dual ?band|hot ?swap\w*|tri ?mode|super ?bass|bass ?boost"
    r"|rgb|motion sensor|solar)"
)
R5_QUALITY_GROUPS: dict[str, tuple[re.Pattern[str], ...]] = {
    # it fits or feels badly in use
    "fit_comfort": _compile(
        (
            rf"(?:masakit|sumasakit|sumakit|nangangawit|nangangalay|makati)\s+(?:(?:sa|ang|yung|ung|ng)\s+)?(?:loob ng\s+)?{_BODY}",
            rf"hurts?\s+(?:(?:my|the)\s+)?{_BODY}",
            r"(?:uncomfortable|not comfortable|hindi comfortable|di comfortable|d comfortable|hindi komportable|di komportable"
            r"|not comfy|hindi comfy)(?!\w)",
            rf"(?:masikip|sobrang sikip|too tight|too big|too small|malaki|maliit)\s+(?:(?:sa|para sa|for)\s+)?(?:(?:my|ko|ng)\s+)?{_BODY}",
            r"falls? out(?:\s+of)?(?:\s+my)?\s+ears?(?!\w)",
            rf"(?:hindi|di|not|doesn't|doesnt)\s+fit\s+(?:(?:sa|in|my)\s+)?{_BODY}",
        )
    ),
    # lag that still works is weak performance; freezing and cutting out are faults
    "lag": _compile(
        (
            r"(?:lag|laggy|lagging|nag ?lalag|naglag|nag ?lag|nagla lag)(?!\w)",
            rf"(?:delay(?:ed)?|late)\s+{_FILL}{{0,2}}(?:cursor|input|pindot|keys?|clicks?|notifs?|notifications?|bluetooth)(?!\w)",
            rf"(?:mabagal|bagal|slow)\s+{_FILL}{{0,2}}(?:response|mag respond|mag ?response|to respond|to wake|cursor)(?!\w)",
        )
    ),
    # the review template's own fields, with a poor answer or a score of 5 out of 10 or lower
    "template_fields": _compile(
        (
            r"(?:sound quality|quality|durability|materials?|build(?: quality)?|comfort|functionality|performance)\s*[:：]\s*"
            r"(?:[\w']+\s+){0,2}?(?:[0-5](?:\.\d)?\s*/\s*10|[0-2](?:\.\d)?\s*/\s*5)(?!\d)",
            r"(?:sound quality|quality|durability|materials?|build(?: quality)?|comfort|functionality)\s*[:：]\s*"
            r"(?:is\s+|very\s+|super\s+|so\s+)?(?:meh|poor|bad|low|cheap|mura|mahina|not good|not great|not really good|pangit"
            r"|panget|sub ?standard|terrible|worst|nakaka ?disappoint\w*|disappointing|basag|sabog|mumurahin)(?!\w)",
        )
    ),
    # a plain verdict on the item's quality
    "verdicts": _compile(
        (
            r"(?:mahinang klase|mababang? (?:ang |yung |ung )?(?:quality|kalidad)|sablay (?:ang |yung |ung )?quality"
            r"|halatang low quality|quality is (?:poor|bad|low|below)|below average quality)(?!\w)",
            r"(?:hindi|di|not)\s+(?:sya\s+|siya\s+|xa\s+)?quality(?:\s+product)?(?:\s*[.!]|\s*$)",
        )
    ),
}
# Damage on the product that leaves it usable, beside COSMETIC (same box guard).
R5_COSMETIC = re.compile(
    r"(?<!\w)(?:may (?:basag|bitak|lamat|crack)|(?:basag|bitak|lamat|crack|cracked)\s+(?:na\s+)?(?:ang|yung|ung|sa|on the|at the)\s+"
    r"(?:likod|gilid|harap|case|casing|cover|takip|frame|body|lens|salamin|ilaw|kanto|stand|tempered glass|glass|tripod|lock|back|side|top|corner)"
    r"|sticky (?:residue|keys?|buttons?)|malagkit)(?!\w)",
    re.IGNORECASE,
)
R5_NAD_GROUPS: dict[str, tuple[re.Pattern[str], ...]] = {
    # guide 1.5, owner's decision: a slow charge against a stated fast-charging claim
    "charging_claim": _compile(
        (
            rf"{_NOT_05}\s+{_SOFT_05}{{0,4}}{_FAST_05}(?!\w)",
            r"(?:charge\w*|charging)\s+(?:speed\s+)?(?:is\s+|still\s+|was\s+)*(?:not|isn't|isnt|wasn't|wasnt)\s+(?:that\s+|so\s+|very\s+)?fast(?!\w)",
            rf"(?:advertised|sold|listed|it says|says)\s+(?:as\s+|it\s+is\s+)?(?:a\s+)?{_FAST_05}(?!\w)",
            r"normal (?:na\s+)?(?:charge\w*|charging)\s+(?:lang|lng|only)(?!\w)",
            r"(?:parang|like a|just a)\s+(?:normal|regular|ordinary)\s+(?:na\s+)?charger(?!\w)",
            rf"(?:akala ko|kala ko|akala q|kala q|i thought)\s+(?:(?:ba|na|sya|siya|it was|it's|its)\s+){{0,2}}{_FAST_05}",
            rf"{_FAST_05}\s+(?:daw|raw)\s+(?:[\w']+\s+){{0,3}}(?:pero|but|tapos|kaso|ang bagal|mabagal|slow)(?!\w)",
        )
    ),
    # a word the product is sold by, named to deny it
    "sold_as_denied": _compile(
        (
            rf"{_NOT_05}\s+{_SOFT_05}{{0,3}}(?:pang\s+|a\s+|an\s+|real\s+)?{_SOLD_AS}(?!\w)",
            rf"{_SOLD_AS}\s+(?:daw|raw)(?!\w)",
            rf"(?:akala ko|kala ko|akala q|kala q|i thought)\s+(?:(?:ba|na|sya|siya|it was|it's|its|is|may|meron)\s+){{0,2}}{_SOLD_AS}(?!\w)",
            rf"supposed to (?:be|have|support)\s+(?:a\s+|an\s+)?(?:{_NUM}\s*{_UNIT}|{_SOLD_AS})(?!\w)",
            rf"(?:it|the box|box|label|title|listing|description|ad|post)\s+says\s+(?:it\s+(?:is|has)\s+)?(?:{_NUM}\s*{_UNIT}|{_SOLD_AS})(?!\w)",
        )
    ),
    # "advertise" spelled without the d, and "as described" forms the served patterns miss
    "advertise_forms": _compile(
        (
            r"not (?:the )?same (?:as |with |sa )?(?:the )?(?:advertise\w*|ads?|listing)(?!\w)",
            r"(?:as|than|from what is|kesa sa|kaysa sa)\s+(?:advertise|advertize\w*)(?!\w)",
            r"(?:fake|misleading|false)\s+(?:info\w*|caption|product name|specs?|claims?)(?!\w)",
        )
    ),
    # a freebie or bundle the listing promised, not received
    "offer_not_received": _compile(
        (
            r"(?:sabi|nakalagay|naka lagay|advertis\w*|listing|description|stated|title|post|ads?)\s+"
            r"(?:(?!(?:not|di|hindi|wala|walang|no)\s)[\w',.!\"]+\s+){0,5}"
            r"[\"']?(?:free|freebies?|bundle|kasama|kasamang|included|includes)\W+(?:[\w',.!\"]+\s+){0,6}?(?:wala|walang|none|no|not|pero|but|tapos|kaso)(?!\w)",
            r"no free\s+(?:[\w']+\s+){0,2}(?:as\s+)?(?:stated|advertised|promised)(?!\w)",
        )
    ),
}
R5_OFF: set[str] = set()
# "hindi rin kami naka experience ng lag", "HND rin masakit sa tainga", "minimal lag":
# r5 reads more spellings of "hindi" and a longer run of words after it.
NEGATED_BEFORE_05 = re.compile(
    r"(?<!\w)(?:wala|walang|hindi|hinde|hind|hndi|hnd|di|d|nd|nde|ndi|no|not|without|zero|never|minimal|doesn't|doesnt"
    r"|don't|dont|isn't|isnt|ni minsan)\s+(?:look\s+|looks\s+|seem\s+|feel\s+)?"
    r"(?:(?:po|pong|naman|namn|nman|nmn|namang|ng|man|talaga|any|kahit|ka|ko|kami|ako|rin|din|naka|nakaka|experience"
    r"|experienced|nakaranas|encounter|encountered|sya|siya|masyado|masyadong|ganun|gaano|gaanong|yung|ung|tipong"
    r"|scratches|dents?|gasgas|or|o|at)\s+){0,5}$",
    re.IGNORECASE,
)


# Revision r6 (17 Oct 2026): both labels, the everyday wordings the served
# patterns and the learned add-on missed. Written after held-out round 15 was
# drawn, from the misses of the served checker on the training rounds (1-14,
# round 14 joining after its single use). Each group is checked on and off over
# every labelled sentence (research/check_r6_rules.py) and judged once on
# held-out round 15 (research/PREREGISTRATION_round15.md). R6_OFF names groups
# switched off, for that check only. Tried and not kept (under 70 in 100 of
# their added flags right): "sobrang liit" and other size words (praise as
# often as a complaint), dirt and dust on arrival, a missing remote (an
# accessory, Rule 1), "palpak" alone (as often said of the seller) and "quick
# charging lang" (no claim named). Taken out after the check: number and
# charging patterns with "fake" in them ("fake fast charger", "fake na
# 20, 000mah"), which moved real possible-fake reports out of that label.
EXTRA_RULES_REVISION_06 = "r6"
# "20, 000mah": the normalizer leaves a space after a thousands comma.
_NUM_06 = r"(?:\d{1,3}(?:,\s?\d{3})+|\d[\d,.]*)"
R6_QUALITY_GROUPS: dict[str, tuple[re.Pattern[str], ...]] = {
    "noise": _compile(
        (
            r"noisy(?!\s+(?:places?|environments?|areas?|rooms?|streets?|surroundings?|backgrounds?|kids|neighbou?rs?))",
            r"noise level\s*:\s*(?:noisy|loud|high|maingay|malakas)",
            r"(?:static|grounded|hissing|buzzing)\s+(?:noise|sound)",
        )
    ),
    # weak air, sound, magnet or picture, said without the served words
    "weak_output": _compile(
        (
            r"(?:not|isn't|isnt|wasn't|wasnt|doesn't feel|does not feel|doesnt feel)\s+(?:(?:that|so|very|really|as|quite)\s+)?strong(?!\w)",
            r"(?:hindi|hinde|di|d|nd|ndi|hnd)\s+(?:(?:sya|siya|xa|ganong|ganun|ganon|gaanong|kasing|masyadong|masyado|po|naman)\s+){1,3}(?:ka)?lakas",
            # "di ko ramdam yung bigat" (I do not feel its weight) is praise
            r"(?:di|hindi|hinde|d|hnd)\s+(?:(?:mo|ko|po|naman|nman|halos)\s+){0,2}(?:ramdam|maramdaman|mafeel)(?!\w)"
            r"(?!\s+(?:(?:yung|ang|ung|ng)\s+)?(?:bigat|weight|init))",
            r"can'?t\s+(?:really\s+)?feel\s+(?:it|the\s+(?:air|wind|breeze|cold))",
            r"(?<!not )(?<!not too )weak(?!\w)(?!\s+(?:charg\w*|battery|signal|spot|points?))",
            r"(?:lacks?|lacking|kulang (?:ng|sa)|walang (?:kahit )?(?:konting |kunting )?)\s*bass",
            r"(?:low|soft)\s+(?:sound|sounds|volume|audio)(?:\s+system)?(?!\w)",
            r"sounds?\s+(?:really\s+|so\s+|very\s+|too\s+)?low",
            rf"(?:audio|sound|voice|mic|cam|camera|picture|video|screen|display|boses|tunog)\s+{_FILL}{{0,2}}(?:is\s+|was\s+)?"
            r"(?:not|hindi|di)\s+(?:so\s+|very\s+|too\s+|that\s+)?(?:clear|cleae|malinaw)",
            r"(?:not|di|hindi)\s+(?:so\s+|very\s+|too\s+)?clear\s+(?:na\s+)?(?:cam|camera|audio|sound|voice|picture)",
            r"(?:muffled|kulob|parang bulong|clouded)",
        )
    ),
    # guide 1.5: an expectation with no claim named is poor quality
    "expectation": _compile(
        (
            r"(?:expected|expecting|i expect|nag ?expect)\s+(?:(?:it|it to|to|na|ako|sana|have|be|a)\s+){0,3}(?:more|better|mas)\s+"
            r"(?:power|bass|volume|lakas|malakas|quality|sound|durability|hangin|strong\w*|loud\w*)",
            r"not as (?:strong|loud|good|malakas) as (?:i\s+)?expect\w*",
        )
    ),
    "cheap_build": _compile(
        (
            r"plastikk?y",
            r"(?:looks?|feels?|mukhang|mukang)\s+(?:so\s+|very\s+|really\s+|super\s+)?cheap(?!\w)",
            r"cheap\s+(?:sound|feel|feeling|build)",
            r"(?:not|poorly|badly)\s+(?:well\s+)?made(?!\w)",
            r"(?:too|so|very|super)\s+thin(?!\w)",
            r"thin\s+(?:wires?|cables?|cords?|materials?|threads?|plastic)",
            r"stiff(?!\w)|matigas\s+(?:ang\s+|yung\s+|ung\s+)?(?:click|pindot\w*|buttons?|keys?|scroll)",
            r"(?:not|hindi|di)\s+(?:so\s+|very\s+)?(?:smooth|madulas)(?!\w)",
            r"(?:ma)?hirap\s+(?:(?:pa|lang|rin|din|mag|nyang|niyang|sya|siya)\s+){0,2}"
            r"(?:pindutin|pindot|i ?switch|buksan|i ?bluetooth|ipair|i ?pair|mag ?type|idrive|i ?drive|i ?press)",
            r"(?:hard|difficult|challenging)\s+to\s+(?:press|pair|click|configure|insert)",
        )
    ),
    "loose_fit": _compile(
        (
            r"loose(?!\s+(?:connection|contact|wires?))",
            r"maluwag(?!\w)",
            r"(?:natatanggal|natatangal|nagdedetach|nagluloose|detach(?:es)?\s+easily|disassembles?\s+easily)",
            r"(?:umuuga|nabubuwal|natutumba|tumutumba|wobbles?)",
        )
    ),
    "verdict_more": _compile(
        (
            r"(?:not reliable|unreliable|unrelible|unrealible)",
            r"quality\s*(?:check)?\s*:?\s*(?:failed|fail)(?!\w)",
            r"lo quality",
            r"(?:di|hindi)\s+(?:ka)?gandahan\s+(?:yung\s+|ang\s+|ung\s+)?quality",
            r"hindi magandang klase",
            r"quality\s+(?:of\s+(?:the\s+)?(?:item|product|cable)\s+)?(?:is|are|was)\s+not\s+(?:quite\s+|so\s+|that\s+|very\s+|as\s+)?good",
            r"(?:audio|sound|mic)\s+(?:and\s+(?:sound|mic|audio)\s+)?quality\s+(?:is|are|was)\s+(?:not good|poor|bad|the worst|worst|terrible)",
            r"disappointed (?:with|in|by) the quality",
        )
    ),
    "audio_more": _compile(
        (
            r"(?:ampanget|ampangit|ang ?panget|ang ?pangit)\s+(?:ng\s+)?(?:tunog|mic|sound|boses|tone)",
            rf"delay(?:ed)?\s+{_FILL}{{0,2}}sounds",
            rf"(?:laro|games?|gaming|videos?|movies?)\s+{_FILL}{{0,2}}(?:delay|late)(?!\w)",
            r"(?:mas malakas|louder)\s+(?:yung\s+|ang\s+|the\s+)?(?:left|right)",
            r"(?:left|right)\s+(?:ear\s*)?(?:pod|piece|side|earbud)?\s*has more bass",
            r"(?:basag|sabog)\s+(?:ang|yung|ung|na)\s+(?:speaker|boses|bosses|bosis|tugtog|music|audio)",
        )
    ),
}
R6_NAD_GROUPS: dict[str, tuple[re.Pattern[str], ...]] = {
    # the review names the listing, its ad, its pictures or its details, and disputes them
    "listing_named": _compile(
        (
            r"wrong(?:ly)?\s+advertis\w*",
            r"(?:pagkaka|pagka)\s*advertis\w*",
            r"(?:doesn'?t|does not|don'?t|didn'?t|did not|won'?t|cannot|can'?t|not|never|hindi|di|wala|walang|no)\s+(?:[\w']+\s+){0,7}?"
            r"(?:as|like|unlike|sa)\s+(?:(?:what\s+)?(?:was|is|it\s+was|they|it'?s)\s+)?"
            r"(?:advertised|advertized|stated|described|promised|indicated|posted|listed|shown|written)(?!\w)",
            r"(?:unlike|contrary to)\s+(?:what\s+)?(?:was\s+|is\s+|they\s+)?(?:advertised|stated|described|posted|indicated|written|shown|listed)",
            r"despite\s+(?:it\s+|its\s+)?(?:being\s+)?(?:advertised|stated|listed|described)",
            r"(?:sabi|sabe|nakalagay|naka lagay|nkalagay|nka lagay|stated|says|said|indicated)\s+(?:(?:po|naman|nila|nyo|niyo|dito|kasi)\s+)?(?:sa|in|on)\s+"
            r"(?:the\s+|their\s+|your\s+|inyong\s+|yung\s+|ang\s+)?(?:advertisement|ad|ads|post|description|discription|picture|pic|photos?|box|manual"
            r"|caption|title|listing|product (?:details|information|description)|page)(?!\w)"
            # the listing cited to confirm it
            r"(?!.*(?:totoo naman|tama naman|legit naman|true naman|accurate naman|satisfied))",
            r"(?:hindi|di|not|doesn'?t|does not)\s+(?:[\w']+\s+){0,2}(?:tugma|match(?:es)?|totoo|true|accurate|aligned?|align|angkop)\s+"
            r"(?:(?:sa|ang|with|to|yung|ung|the)\s+){1,2}(?:[\w']+\s+){0,2}"
            r"(?:description|discription|pic|pics|picture|pictures|photos?|specs?|details|information|info|listing|ads?|advertisement|post)(?!\w)",
            r"(?:true|honest)\s+(?:to|sa)\s+(?:the\s+|your\s+|inyong\s+|ang\s+)?(?:product\s+)?(?:details|description|specs|ads?|post|listing)",
            r"(?:description|picture|photo|ads?)\s+(?:versus|vs\.?)\s+reality|(?:expecting|expected)\s+vs\.?\s+reality",
            r"(?:different|off)\s+from\s+what\s+(?:(?:is|was)|the\s+\w+\s+(?:is|was))\s+(?:listed|shown|showing|posted|stated|advertised|described)",
            r"not\s+(?:like\s+)?what(?:'s|s| is| was)?\s+(?:written|posted|indicated|stated|shown|listed|advertised|in the (?:specs|description|picture))",
            r"not\s+whats?\s+in\s+(?:the\s+)?specs",
            r"(?:edit|palitan|change|pakiedit|update)\s+(?:(?:ng|ang|yung|nyo|niyo|po|the|your|item)\s+){0,3}"
            r"(?:caption|description|item description|pictures?|title|product name)",
            r"(?:deceptive|deceiving|deception)",
        )
    ),
    # a stated number doubted or denied, in wordings the served patterns miss
    "number_doubt": _compile(
        (
            rf"not\s+actually\s+(?:a\s+)?{_NUM_06}",
            rf"(?:hindi|di|not)\s+(?:(?:siya|sya|xa|cia|naman|po|ito|to)\s+){{0,2}}(?:talaga(?:ng)?|tlga|totoong|legit\s+na|really|actually)\s+{_NUM_06}",
            rf"(?:don'?t|dont|do not)\s+(?:think|believe)\s+(?:that\s+)?(?:it'?s|its|it is|this is)?\s*(?:actually\s+|really\s+|talaga(?:ng)?\s+)?{_NUM_06}\s*{_UNIT}",
            rf"(?:parang|mukhang|mukang)\s+(?:hindi|di)\s+(?:(?:sya|siya|xa|ito|to)\s+)?{_NUM_06}\s*{_UNIT}",
            rf"(?:to think na|to think that|considering|although|despite(?:\s+it)?(?:\s+being)?|even though it'?s)\s+(?:(?:it'?s|its|sya|siya)\s+)?{_NUM_06}\s*{_UNIT}",
            rf"(?:the\s+)?{_NUM_06}\s*{_UNIT}\s+(?:is|na|ay)\s+(?:false|scam|not true)",
            rf"(?:sabi|sabe|nakalagay|naka lagay|nkalagay|nka lagay|description|stated|advertised|akala ko|kala ko|akala q|kala q|i thought(?: of| that)?)\s+"
            rf"{_FILL}{{0,4}}{_NUM_06}\s*{_UNIT}(?!\w)",
            rf"{_NUM_06}\s*{_UNIT}\s+(?:(?:po|lang|daw)\s+)?(?:nakalagay|naka lagay|nkalagay|nka lagay|sa box|on the box|sa kahon)",
            r"(?:nakalagay|naka lagay|nkalagay)\s+(?:(?:sa\s+(?:box|kahon)|po|naman)\s+)?\d{4,}",
            rf"(?:never|not)\s+(?:a\s+|the\s+)?(?:full\s+)?capacity\s+of\s+{_NUM_06}",
            rf"capacity\s+(?:is|was)\s+(?:just|only)\s+(?:around\s+|about\s+)?{_NUM_06}",
            rf"(?:sabi|sabe|nakalagay|nklagay|nka lagay|naka lagay|akala ko|kala ko|advertis\w*|stated|says?)\s+{_FILL}{{0,4}}(?:up to\s+)?{_NUM_06}\s*(?:hours?|hrs?)(?!\w)",
            rf"far\s+from\s+{_NUM_06}",
            rf"disguised\s+as\s+(?:a\s+)?{_NUM_06}",
        )
    ),
    # "20kmAh ?": a stated number asked back
    "number_question": _compile((rf"{_NUM_06}\s*{_UNIT}\s*\?",)),
    # guide 1.5: a charging claim denied, in wordings charging_claim (r5) misses
    "charging_more": _compile(
        (
            r"not\s+(?:so|super|really|that|very|even)\s+(?:fast|quick)(?:\s+charg\w*)?(?!\w)"
            r"(?!\s+(?:delivery|shipping|ship|deliver\w*|shipment|response|reply|air|blow\w*|wind|hangin))",
            r"charg\w*\s*(?:speed)?\s*:?\s*(?:is\s+|was\s+)?not\s+(?:so\s+|super\s+|really\s+|that\s+|very\s+)?fast",
            r"not\s+charg\w*\s+fast",
            r"(?:no|wala(?:ng)?)\s+fast\s+charg\w*(?!\w)(?!\s+(?:needed|required|necessary))",
            r"fast\s+charg\w*\s+(?:is\s+|was\s+|feature\s+)?(?:not working|doesn'?t work|does not work|hindi gumagana|di gumagana)",
            r"(?:hindi|di|hind|not)\s+(?:legit|totoo|totoong|true)\s+(?:na\s+)?(?:fast|pas|past)\s*charg\w*",
            r"(?:doesn'?t|does not|don'?t|won'?t|not|hindi|di|cannot|can'?t)\s+(?:(?:support|activate|reach|do|give|compatible|with)\w*\s+){1,2}"
            r"(?:(?:the|with|sa|ng|yung)\s+)?(?:mi\s+|xiaomi\s+|\"mi\s+)?(?:turbo|dart|super ?vooc|vooc|warp|super ?charg\w*|\d+\s*w(?:atts?)?)(?!\w)",
            r"(?:not|hindi|di)\s+(?:xiaomi\s+)?\"?(?:mi\s+)?(?:turbo|dart)(?!\w)",
            r"(?:slow|mabagal)\s+(?:charg\w*\s+)?(?:despite|even though|although)",
            r"so\s*called\s+fast\s+charg\w*",
            r"(?:akala ko|kala ko|i thought)\s+(?:[\w']+\s+){0,3}(?:mi\s+)?(?:turbo|fast|super ?fast|dart|vooc)\s*charg\w*",
        )
    ),
    # a feature the product is sold by, absent
    "feature_absent": _compile(
        (
            r"(?:walang|wala\s+(?:sya|syang|siyang|po|pong|naman|itong)|there is no|there'?s no|without|no)\s+(?:(?:active|actual|real)\s+)?"
            r"(?:noise ?cancel\w*|anc|enc|anr|flash ?light|blue ?light|sensor|wireless charg\w*|magsafe)(?!\w)(?!\s+(?:issues?|problems?|problema))",
            r"(?:is\s+|it'?s\s+)?not\s+(?:an?\s+)?(?:anr|anc|active noise\w*)(?!\w)",
        )
    ),
}
R6_OFF: set[str] = set()


# Revision r7 (17 Oct 2026): both labels, more everyday wordings, and two r6
# mistakes. Written after held-out round 16 was drawn, from the misses and
# false flags of the served checker (r6) on the training rounds 1-15 (round 15
# joining after its single use). Each group is checked on and off over every
# labelled sentence (research/check_r7_rules.py) and judged once on held-out
# round 16 (research/PREREGISTRATION_round16.md). R7_OFF names parts switched
# off, for that check only: the groups below, "thin" (r6's "very thin", said in
# praise of a slim power bank, narrowed) and "negation" (the denial guard reads
# "wasn't that noisy"). Tried and not kept: a feature said to be absent
# ("walang bluetooth", "no display"; as often a fault or a missing part) and
# "not type C" (a wrong part sent, Rule 1).
# Judged once on held-out round 16 (research/round16_test.json): the
# poor-quality parts adopted (weighted F1 0.622 -> 0.627); the not-as-advertised
# groups NOT adopted (0.507 -> 0.500: their one change on the round was a false
# flag, "legit naman based on the specs in the ad"). R7_NAD_GROUPS stay below
# for the record and are not read; r7 reads not as advertised as r6 does.
EXTRA_RULES_REVISION_07 = "r7"
R7_QUALITY_GROUPS: dict[str, tuple[re.Pattern[str], ...]] = {
    "sound_more": _compile(
        (
            r"no\s+bass(?!\w)|(?:need|needs|kulang)\s+(?:(?:more|ng|pa|meron)\s+){0,2}bass",
            r"(?:has|may|with|meron(?:g)?)\s+(?:(?:a|some|konting|kunting)\s+)?(?:static|echo|hissing|humming|ugong|feed ?back)(?!\w)",
            r"humming(?!\w)",
            r"(?:matinis|garal gal|ngungu|trumpeta|tumpag)(?!\w)",
            r"not as (?:loud|strong|clear|good|fast|malakas) (?:as )?(?:i|we) (?:wanted|hoped|thought|expected)",
            r"(?:sound|tunog)\s+(?:is\s+)?not\s+even|uneven\s+(?:sound|volume)",
            r"(?:mura|cheap)\s+(?:(?:din|dn|rin|rn|ang|yung)\s+)?(?:tunog|sound)(?!s)",
            rf"baliktad\s+{_FILL}{{0,3}}(?:left|right|sound|tunog)|(?:right|left)\s+(?:and\s+(?:left|right)\s+)?(?:speakers?|sound)\s+(?:are|is)\s+(?:wrong|reversed|swapped)",
        )
    ),
    "fit_more": _compile(
        (
            r"maluwang\s+(?:(?:sya|siya|po|na|ang|yung|ung|sa|siya sa|sya sa)\s+){0,2}(?:[\w']+\s+){0,1}(?:phone|cp|tenga|tainga|ears?|outlet|socket|port|usb|plug|cord|case|kamay|ulo|head)",
            r"(?:phone|cp|plug|port|usb|socket|clip|saksakan|pangsaksak|jack)\s+(?:[\w']+\s+){0,2}maluwang(?!\w)",
            r"(?:if|kung)\s+(?:you\s+have|may)\s+(?:tiny|small|maliit na)\s+ears|(?:i\s+(?:do\s+)?have|may)\s+(?:big|malaki(?:ng)?)\s+(?:ears|tenga)",
            r"(?:not|hindi|di)\s+(?:very\s+|so\s+)?tight\s+(?:in|sa)(?!\w)",
            r"(?:don'?t|do not|doesn'?t|does not|hindi|di)\s+(?:[\w']+\s+)?fit\s+(?:in|sa)\s+(?:the\s+)?(?:plugs?|ports?|outlet|socket|phone|case)",
        )
    ),
    "template_more": _compile(
        (
            r"(?:speed settings?|ease of use|ergonomics|design|appearance|portability|noise level|connectivity|connection speed)\s*[:：]\s*"
            r"(?:[\w']+\s+){0,2}?(?:[0-4](?:\.\d)?\s*/\s*10|[0-2](?:\.\d)?\s*/\s*5)(?!\d)",
            r"(?:speed settings?|ease of use|portability|design|connectivity|connection speed)\s*[:：]\s*(?:is\s+|very\s+)?"
            r"(?:poor|bad|meh|not good|pangit|panget|mahina|terrible)(?!\w)",
        )
    ),
    "weak_more": _compile(
        (
            r"(?:hindi|di|d|hinde)\s+(?:(?:sya|siya|naman|nmn|nman|po)\s+)?(?:gnun|gaano|gano|ganong|ganun|ganon)\s+(?:ka)?(?:lakas|malakas|mahangin|lamig|malamig)",
            r"(?:di|hindi)\s+(?:(?:nman|naman|po)\s+)?malamig\s+(?:yung|ang|ung)\s+(?:hangin|hanging)",
            r"mas malakas pa\s+(?:[\w']+\s+){6,8}(?:kesa|kaysa|than)(?!\w)",
            r"mas malakas pa\s+(?:(?:ang|yung|ung|pag)\s+)?(?:boses|ihip|liwanag|record)\s+(?:ko|nung|ng)",
            r"(?:nahihinaan|nahinaan)(?!\w)",
            r"(?:short|maiksi|maikli)\s+(?:(?:lng|lang|ang)\s+)*(?:bluetooth\s+)?range|range\s+(?:is\s+)?(?:short|poor|weak)|di ok (?:ung|yung|ang) range",
        )
    ),
    "cheap_more": _compile(
        (
            r"(?:subpar|sub par|low grade|lower quality|mababang klase)(?!\w)",
            r"quality\s*,?\s+(?:super|very|so|sobrang)\s+(?:low|bad|poor)",
            r"(?:it'?s\s+)?a\s+toy\s+(?:headphone|watch|speaker|fan|mouse)|laruan\s+(?:lang|lng|pa|ang dumating|na relo)",
            r"(?:surface|material|materials|build|finish|plastic|tela|wire|cable)\s+(?:is|are|was)\s+not\s+(?:that|so|very)\s+good",
            r"improper\s+assembly",
        )
    ),}
_VERY_THIN_06 = next(p for p in R6_QUALITY_GROUPS["cheap_build"] if p.pattern.endswith(r"(?:too|so|very|super)\s+thin(?!\w))"))
THIN_07 = _compile((r"(?:too|so)\s+thin(?!\w)", r"(?:very|super)\s+thin\s+(?:wires?|cables?|cords?|materials?|plastic|threads?)"))
NEGATED_BEFORE_07 = re.compile(
    NEGATED_BEFORE_05.pattern.replace(
        r"|don't|dont|isn't|isnt|ni minsan)",
        r"|don't|dont|isn't|isnt|wasn't|wasnt|was not|is not|aren't|arent|weren't|werent|ni minsan)",
    ).replace(r"|or|o|at)\s+){0,5}$", r"|or|o|at|that|so|very|too|really)\s+){0,5}$"),
    re.IGNORECASE,
)
R7_NAD_GROUPS: dict[str, tuple[re.Pattern[str], ...]] = {
    "charging_r7": _compile(
        (
            r"(?:not|hindi|di|d|hind)\s+(?:(?:sya|siya|cia|xa|po|naman|nman|truely|truly|really|tunay|totoo|totoong|true|legit)\s+){0,3}(?:na\s+)?"
            r"(?:fast|pass|pas|past|super)\s*(?:charg\w*|changer|changing|chrger|chager|chaeger|chargs)(?!\w)",
            r"(?:i thought|akala ko|kala ko|kala q|akala q)\s+(?:(?:naman|nman|ba|na|sya|siya|it'?s|its|it was)\s+){0,2}(?:fast|turbo|super ?fast)(?:\s*(?:charg\w*|changer))?(?!\w)"
            r"(?!\s+(?:delivery|shipping|ship|deliver\w*|dating|dumating|response|reply|transaction))",
            rf"(?:don'?t|dont|do not)\s+believe\s+{_FILL}{{0,3}}fast\s*charg\w*",
            r"(?:doesn'?t|does not|not)\s+(?:indicat\w*|show\w*|display\w*)\s+(?:(?:as|that|it'?s|its)\s+){0,2}(?:fast|turbo|super)\s*charg\w*",
            r"not\s+(?:efficient|powerful|fast|quick)\s+power\s+output",
            r"(?:same as|para lang(?: din)?(?: na| ng)?|just like)\s+(?:a\s+|an\s+)?(?:regular|normal|ordinary)\s+(?:na\s+)?(?:cable|charger|charging|cord)",
            r"not\s+even\s+(?:quick|fast|medium speed|super)\s*charg\w*",
        )
    ),
    "listing_r7": _compile(
        (
            rf"{_NUM_06}\s*{_UNIT}\s+(?:sa|in|on)\s+(?:the\s+)?(?:ads?|adds|post|picture|pic|description|video|listing|box|kahon)(?!\w)",
            rf"(?:hindi|di)\s+(?:(?:sya|siya|ito|to|naman|po)\s+)?(?:yung|ung|ang|katulad|kagaya|gaya|tulad)\s+{_FILL}{{0,2}}(?:nasa|sa)\s+(?:larawan|litrato)",
            rf"(?:hindi|di)\s+(?:(?:niya|nya|sya|siya)\s+)?(?:kapareha|kapareho|kamukha|katulad|kagaya)\s+{_FILL}{{0,3}}(?:nakapost|naka post|posted|post|larawan|litrato|picture|pic|photo|ads?)(?!\w)",
            rf"nag\s*post\s+{_FILL}{{0,3}}(?:na\s+)?(?:hindi|di|wala)(?!\w)",
            rf"(?:documentation|manual|box|label|packaging|specs?|it)\s+(?:says?|said|states?)\s+(?:that\s+)?(?:it'?s\s+|it is\s+|na\s+)?(?:a\s+)?{_NUM_06}\s*{_UNIT}(?!\w)",
            r"specs?\s+(?:on|sa|in)\s+(?:the\s+)?(?:ads?|adds|post|description)",
            r"expectations?\s+(?:versus|vs\.?)\s+reality",
            r"what (?:you|u) see is not what (?:you|u) get",
            rf"(?:sabi|ang sabi|nakalagay|naka lagay)\s+(?:(?:may|meron|ay|na|daw|po)\s+){{0,2}}{_FILL}{{0,2}}(?:free|freebies?)(?!\w)",
            rf"(?:kahit|although|even though)\s+{_FILL}{{0,1}}(?:3|4|5)\s*in\s*1",
        )
    ),
    "fake_feature": _compile(
        (
            r"(?:display(?: board)?|meter|read ?out|battery meter|percentage|percent)\s+(?:is\s+|nya\s+)?(?:fake|peke)|fake\s+(?:display|meter|battery meter|read ?out|percent\w*)",
            r"(?:capacity|charging speed|output|wattage)\s*[:：]\s*(?:fake|peke|false|not true|scam)(?!\w)",
        )
    ),}
R7_OFF: set[str] = set()


def _r5_patterns(groups: dict[str, tuple[re.Pattern[str], ...]]) -> tuple[re.Pattern[str], ...]:
    return tuple(pattern for name, patterns in groups.items() if name not in R5_OFF for pattern in patterns)


def _r6_patterns(groups: dict[str, tuple[re.Pattern[str], ...]]) -> tuple[re.Pattern[str], ...]:
    return tuple(pattern for name, patterns in groups.items() if name not in R6_OFF for pattern in patterns)


def _r7_patterns(groups: dict[str, tuple[re.Pattern[str], ...]]) -> tuple[re.Pattern[str], ...]:
    return tuple(pattern for name, patterns in groups.items() if name not in R7_OFF for pattern in patterns)


def not_as_described_spans(normalized: str, revision: str = EXTRA_RULES_REVISION) -> list[tuple[int, int]]:
    """Where the reviewer disputes a number, a feature or the photos."""
    patterns = NOT_AS_DESCRIBED_PATTERNS
    if revision in (EXTRA_RULES_REVISION_05, EXTRA_RULES_REVISION_06, EXTRA_RULES_REVISION_07):
        patterns = patterns + _r5_patterns(R5_NAD_GROUPS)
    if revision in (EXTRA_RULES_REVISION_06, EXTRA_RULES_REVISION_07):
        patterns = patterns + _r6_patterns(R6_NAD_GROUPS)
    spans = [
        found.span()
        for pattern in patterns
        for found in pattern.finditer(normalized)
        if not SPECULATION.search(normalized[: found.start()]) and "dual shock" not in found.group(0).casefold()
    ]
    for found in ONLY_NUMBER.finditer(normalized):
        before = normalized[: found.start()]
        if (
            OWN_DEVICE_AFTER.match(normalized[found.end():])
            or CONCESSION_BEFORE.search(before)
            or OWN_DEVICE_BEFORE.search(before)
        ):
            continue
        spans.append(found.span())
    for found in COMPARED_TO_SHOWN.finditer(normalized):
        if not PRAISE_BEFORE.search(normalized[: found.start()]):
            spans.append(found.span())
    return sorted(set(spans))


# "pag mahina lang ang volume": a condition, not a complaint.
CONDITION_BEFORE = re.compile(r"(?<!\w)(?:pag|kapag|kung|if|when)\s+(?:[\w']+\s+){0,1}$", re.IGNORECASE)
# "ang hina na nya mag charge": slow charging is a defect (guide 1.3), not poor quality.
CHARGING_AFTER = re.compile(r"\s*(?:[\w']+\s+){0,3}(?:mag ?charge|magcharge|charge)(?!\w)", re.IGNORECASE)


def _on_the_box(normalized: str, span: tuple[int, int], reach: int = 5) -> bool:
    before = re.findall(r"[\w']+", normalized[: span[0]])[-reach:]
    after = re.findall(r"[\w']+", normalized[span[1]:])[:reach]
    return any(word in PACKAGING for word in before + after)


def quality_spans(normalized: str, revision: str = EXTRA_RULES_REVISION) -> list[tuple[int, int]]:
    """Where the reviewer says the product is weak, cheap, flimsy or marked."""
    patterns, negated_before = (
        (QUALITY_PATTERNS_04, NEGATED_BEFORE_04) if revision == EXTRA_RULES_REVISION_04 else (QUALITY_PATTERNS, NEGATED_BEFORE)
    )
    if revision in (EXTRA_RULES_REVISION_05, EXTRA_RULES_REVISION_06, EXTRA_RULES_REVISION_07):
        patterns = QUALITY_PATTERNS_04 + _r5_patterns(R5_QUALITY_GROUPS)
        negated_before = NEGATED_BEFORE_04 if "negation" in R5_OFF else NEGATED_BEFORE_05
    if revision in (EXTRA_RULES_REVISION_06, EXTRA_RULES_REVISION_07):
        patterns = patterns + _r6_patterns(R6_QUALITY_GROUPS)
    if revision == EXTRA_RULES_REVISION_07:
        if "thin" not in R7_OFF:
            patterns = tuple(pattern for pattern in patterns if pattern is not _VERY_THIN_06) + THIN_07
        patterns = patterns + _r7_patterns(R7_QUALITY_GROUPS)
        if "negation" not in R7_OFF:
            negated_before = NEGATED_BEFORE_07
    spans = [
        found.span()
        for pattern in patterns
        for found in pattern.finditer(normalized)
        if not negated_before.search(normalized[: found.start()])
        and not NEGATED_INSIDE.search(found.group(0))
        and not HEARSAY_BEFORE.search(normalized[: found.start()])
        and not CONDITION_BEFORE.search(normalized[: found.start()])
        and not ("hina" in found.group(0).casefold() and CHARGING_AFTER.match(normalized[found.end():]))
    ]
    later = revision in (EXTRA_RULES_REVISION_05, EXTRA_RULES_REVISION_06, EXTRA_RULES_REVISION_07)
    cosmetic = (COSMETIC, R5_COSMETIC) if later and "cosmetic" not in R5_OFF else (COSMETIC,)
    spans += [
        found.span()
        for regex in cosmetic
        for found in regex.finditer(normalized)
        if not negated_before.search(normalized[: found.start()]) and not _on_the_box(normalized, found.span())
        and not PROTECTIVE_BEFORE.search(normalized[: found.start()])
        and not PROTECTIVE_AFTER.match(normalized[found.end():])
    ]
    return sorted(set(spans))
