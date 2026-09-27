"""Hand-written metadata for the demo collection's files, keyed by filename.

This is what the fake vision adapter answers, so the pipeline, the UI and search can be run on
the real demo files without calling a model. Written in the style of a real answer: the fixed
type tags are left out, because normalisation adds them to every answer alike.
"""

from kms.ai.schema import Metadata

FIXTURES: dict[str, Metadata] = {
    # --- images --------------------------------------------------------------
    "IMG_2101.jpg": Metadata(
        title="Car key on a red umbrella hook",
        description=(
            "A black car key with a Nissan logo and a metal blade hangs from a key ring on a "
            "small red umbrella-shaped wall hook. A second, orange umbrella hook is on the plain "
            "white wall to the right."
        ),
        tags=[
            "car key",
            "key",
            "keys",
            "hook",
            "umbrella",
            "red",
            "orange",
            "wall",
            "nissan",
            "key ring",
            "home",
            "hallway",
        ],
        visible_text="",
        image_type="photo",
    ),
    "IMG_2114.jpg": Metadata(
        title="El Al plane at an airport gate",
        description=(
            "A white El Al passenger jet with a blue stripe and a Star of David on the tail is "
            "parked at a jet bridge, seen through a terminal window. Baggage carts loaded with "
            "suitcases and ground crew in high-visibility vests stand on the apron; an easyJet "
            "plane is parked behind under a cloudy sky."
        ),
        tags=[
            "airplane",
            "plane",
            "aircraft",
            "airport",
            "el al",
            "easyjet",
            "gate",
            "jet bridge",
            "baggage carts",
            "luggage",
            "apron",
            "ground crew",
            "travel",
            "cloudy sky",
        ],
        visible_text="ELAL אל על\neasyJet\n3312 7852 7788 7664",
        image_type="photo",
    ),
    "IMG_2140.jpg": Metadata(
        title="Crowd in front of the Pantheon, Rome",
        description=(
            "The columned portico of the Pantheon in Rome with an inscription above the columns, "
            "and a tall obelisk rising from a fountain in the square. A large crowd of tourists "
            "sits on the fountain steps and walks across the square under a blue sky with white "
            "clouds."
        ),
        tags=[
            "pantheon",
            "rome",
            "italy",
            "crowd",
            "tourists",
            "people",
            "obelisk",
            "fountain",
            "square",
            "columns",
            "ancient",
            "architecture",
            "landmark",
            "blue sky",
            "clouds",
        ],
        visible_text="M·AGRIPPA·L·F·COS·TERTIVM·FECIT",
        image_type="photo",
    ),
    "IMG_2152.jpg": Metadata(
        title="Two flower-shaped gelato cones",
        description=(
            "Two hands hold ice cream cones over a wooden table, each scoop shaped like a rose "
            "with petals of mango and vanilla gelato. White paper napkins lie on the table; "
            "people sit blurred in the background of a café."
        ),
        tags=[
            "ice cream",
            "gelato",
            "cone",
            "dessert",
            "flower",
            "rose",
            "mango",
            "vanilla",
            "yellow",
            "hands",
            "table",
            "napkins",
            "café",
            "sweet",
        ],
        visible_text="",
        image_type="photo",
    ),
    "IMG_2167.jpg": Metadata(
        title="Stone fort and watchtower above the sea",
        description=(
            "A pale stone fortress wall runs along the water to a round watchtower with a domed "
            "top. Below, calm blue sea meets a rocky shore and a breakwater, with hills on the "
            "horizon under a clear sky."
        ),
        tags=[
            "fort",
            "fortress",
            "tower",
            "watchtower",
            "stone wall",
            "sea",
            "harbour",
            "breakwater",
            "coast",
            "rocks",
            "marseille",
            "france",
            "blue sky",
            "summer",
        ],
        visible_text="",
        image_type="photo",
    ),
    "IMG_2168.jpg": Metadata(
        title="Hotel guest registration form",
        description=(
            "A printed guest registration form from Hôtel des Deux Phares in Marseille, filled "
            "in by hand in blue ink, lying at an angle on a grey surface. It lists the guest's "
            "name, nationality, arrival and departure dates, room number and passport as ID, "
            "and is signed at the bottom."
        ),
        tags=[
            "form",
            "registration",
            "hotel",
            "paperwork",
            "check-in",
            "guest",
            "marseille",
            "handwriting",
            "signature",
            "passport",
            "french",
            "paper",
        ],
        visible_text=(
            "HÔTEL DES DEUX PHARES\nQuai du Port · 13002 Marseille\n"
            "FICHE D'ARRIVÉE / GUEST REGISTRATION FORM\n"
            "Nom / Surname Cohen\nPrénom / First name Daniel\nNationalité / Nationality Israeli\n"
            "Date d'arrivée / Arrival 13 / 08 / 2026\nDate de départ / Departure 16 / 08 / 2026\n"
            "Chambre / Room 214\nNombre de personnes / Guests 2\n"
            "Adresse / Home address (on file)\nPièce d'identité / ID document Passport\n"
            "Je certifie l'exactitude des renseignements ci-dessus.\n"
            "I certify that the information above is correct.\nSignature:\n"
            "Réception · ouverte 24h/24"
        ),
        image_type="document",
    ),
    "IMG_2203.jpg": Metadata(
        title="Tottenham Court Road Underground sign",
        description=(
            "The red and blue roundel sign of the London Underground reading Tottenham Court "
            "Road, on a white tiled station wall above a grey metal platform bench with a "
            "yellow armrest."
        ),
        tags=[
            "underground",
            "tube",
            "subway",
            "metro",
            "station",
            "platform",
            "roundel",
            "sign",
            "london",
            "tottenham court road",
            "tiles",
            "bench",
            "transport",
        ],
        visible_text="TOTTENHAM COURT ROAD",
        image_type="photo",
    ),
    "IMG_2218.jpg": Metadata(
        title="Two cocktails at a Greenwich bar",
        description=(
            "Two hands raise tall glasses of pale green cocktails with lime and black straws "
            "at a wooden bar counter. Behind them, shelves of lit bottles sit under a gold "
            "lettered sign, next to a Guinness tap and a potted plant."
        ),
        tags=[
            "cocktail",
            "drinks",
            "bar",
            "pub",
            "glass",
            "lime",
            "elderflower",
            "st-germain",
            "guinness",
            "bottles",
            "greenwich",
            "cheers",
            "evening",
        ],
        visible_text="GREENWICH\nST-GERMAIN\nGUINNESS",
        image_type="photo",
    ),
    "IMG_2225.jpg": Metadata(
        title="Restaurant receipt, The Lantern & Anchor",
        description=(
            "A printed restaurant receipt from The Lantern & Anchor in Greenwich, London, on a "
            "wooden table. It lists fish and chips, mussels, two elderflower spritzes and "
            "sticky toffee pudding, with a total of 76.95 GBP paid by Visa."
        ),
        tags=[
            "receipt",
            "bill",
            "restaurant",
            "dinner",
            "payment",
            "total",
            "price",
            "greenwich",
            "london",
            "fish and chips",
            "visa",
            "paper",
        ],
        visible_text=(
            "THE LANTERN & ANCHOR\nRiverside Kitchen & Bar\nGreenwich, London SE10\n"
            "Table 12 Covers 2\n09/08/2026 20:47\n"
            "1 Fish & chips 18.50\n1 Mussels, white wine 16.00\n1 Side mushy peas 4.00\n"
            "2 Elderflower spritz 19.00\n1 Sticky toffee pudding 7.50\n1 Sparkling water 3.40\n"
            "Subtotal 68.40\nService 12.5% 8.55\nTOTAL GBP 76.95\nVISA **** 4417 76.95\n"
            "VAT No. 000 0000 00\nThank you - see you again!"
        ),
        image_type="document",
    ),
    "IMG_2231.jpg": Metadata(
        title="Tower Bridge over the Thames",
        description=(
            "Tower Bridge in London with its two stone Gothic towers and pale blue suspension "
            "chains, seen from the riverbank across the brown water of the Thames. Tourist "
            "boats are moored on the left and modern buildings stand on the right under a "
            "clear blue sky."
        ),
        tags=[
            "bridge",
            "tower bridge",
            "tower",
            "london",
            "thames",
            "river",
            "water",
            "landmark",
            "architecture",
            "boats",
            "blue sky",
            "sunny",
        ],
        visible_text="",
        image_type="photo",
    ),
    "IMG_2240.jpg": Metadata(
        title="Big Ben with a red double-decker bus",
        description=(
            "The Elizabeth Tower, Big Ben, rises above the Houses of Parliament under a blue "
            "sky with clouds. In the street below, a red double-decker bus and black London "
            "cabs wait in traffic."
        ),
        tags=[
            "big ben",
            "clock tower",
            "clock",
            "tower",
            "london",
            "westminster",
            "parliament",
            "double-decker bus",
            "red bus",
            "black cab",
            "taxi",
            "traffic",
            "street",
            "landmark",
        ],
        visible_text="Go\nFulham Broadway",
        image_type="photo",
    ),
    "IMG_2305.jpg": Metadata(
        title="Waterfall under a wooden footbridge",
        description=(
            "A waterfall pours down a smooth granite chute into a clear green pool, with mossy "
            "rock walls on both sides. A wooden footbridge crosses the gorge at the top, and "
            "ferns and leaves catch the sunlight."
        ),
        tags=[
            "waterfall",
            "falls",
            "gorge",
            "footbridge",
            "bridge",
            "wooden",
            "rocks",
            "granite",
            "pool",
            "stream",
            "moss",
            "ferns",
            "forest",
            "hiking",
            "nature",
        ],
        visible_text="",
        image_type="photo",
    ),
    "IMG_2311.jpg": Metadata(
        title="Tall waterfall in a rocky gorge",
        description=(
            "A tall, narrow waterfall falls in a smooth white ribbon between grey and brown "
            "rock faces, taken with a long exposure. Bright green trees grow on the right side "
            "of the cliff."
        ),
        tags=[
            "waterfall",
            "falls",
            "long exposure",
            "cliff",
            "rock",
            "gorge",
            "trees",
            "forest",
            "green",
            "nature",
            "mountains",
            "hiking",
        ],
        visible_text="",
        image_type="photo",
    ),
    "IMG_2326.jpg": Metadata(
        title="Red sports car on a mountain top",
        description=(
            "A red Chevrolet Corvette sports car is parked in a gravel lot on a mountain summit, "
            "next to a dark minivan. Behind them, hazy blue mountain ridges stretch to the "
            "horizon under white clouds."
        ),
        tags=[
            "sports car",
            "car",
            "red",
            "corvette",
            "chevrolet",
            "minivan",
            "parking",
            "gravel",
            "mountain",
            "summit",
            "view",
            "clouds",
            "road trip",
        ],
        visible_text="",
        image_type="photo",
    ),
    "IMG_2327.jpg": Metadata(
        title="Hazy mountain ridges",
        description=(
            "Layer after layer of forested mountain ridges fade into blue haze toward the "
            "horizon, seen from a high viewpoint. White clouds float in a pale blue sky above."
        ),
        tags=[
            "mountains",
            "ridges",
            "haze",
            "valley",
            "view",
            "landscape",
            "forest",
            "blue",
            "clouds",
            "sky",
            "summit",
            "nature",
        ],
        visible_text="",
        image_type="photo",
    ),
    "IMG_2402.jpg": Metadata(
        title="Clock tower lit up at night",
        description=(
            "A tall office clock tower lit against the night sky, with a glowing white clock "
            "face, a white pyramid spire and a gold lantern on top. Lit windows fill the "
            "neighbouring buildings, and dark trees line the bottom of the frame."
        ),
        tags=[
            "clock tower",
            "tower",
            "clock",
            "night",
            "city",
            "skyscraper",
            "lights",
            "illuminated",
            "spire",
            "new york",
            "madison square park",
            "architecture",
        ],
        visible_text="",
        image_type="photo",
    ),
    "IMG_2403.jpg": Metadata(
        title="Clock tower and skyline at night",
        description=(
            "A lit clock tower with a white spire and gold top rises behind park trees at "
            "night, between taller glass skyscrapers with lit windows. A red traffic light and "
            "a street lamp glow in the foreground."
        ),
        tags=[
            "clock tower",
            "tower",
            "night",
            "city",
            "skyline",
            "skyscrapers",
            "lights",
            "park",
            "trees",
            "traffic light",
            "new york",
            "evening",
        ],
        visible_text="",
        image_type="photo",
    ),
    "IMG_2417.jpg": Metadata(
        title="Warhol soup cans in a museum",
        description=(
            "Rows of framed paintings of Campbell's soup cans hang in a long grid on a white "
            "gallery wall, each can red and white with a different flavour. The wooden floor "
            "of the museum shows at the bottom left."
        ),
        tags=[
            "art",
            "museum",
            "gallery",
            "painting",
            "pop art",
            "warhol",
            "campbell's",
            "soup cans",
            "frames",
            "exhibition",
            "red",
            "white",
        ],
        visible_text=(
            "Campbell's CONDENSED TURKEY VEGETABLE SOUP\nCampbell's CONDENSED CHILI BEEF SOUP\n"
            "Campbell's CONDENSED VEGETABLE BEAN SOUP\nCampbell's CONDENSED CHICKEN NOODLE SOUP\n"
            "Campbell's CONDENSED CREAM OF MUSHROOM SOUP\n"
            "Campbell's CONDENSED SCOTCH BROTH (A HEARTY SOUP) SOUP"
        ),
        image_type="photo",
    ),
    "IMG_2450.jpg": Metadata(
        title="Bag of banana Bamba peanut butter puffs",
        description=(
            "A hand holds up a yellow bag of Bamba banana-flavoured peanut butter puffs in a "
            "shop aisle, with a picture of the puffed snacks on the front. Cartons and more "
            "bags of Bamba are stacked behind it."
        ),
        tags=[
            "snack",
            "bamba",
            "peanut butter",
            "puffs",
            "banana",
            "bag",
            "packaging",
            "yellow",
            "shop",
            "grocery",
            "food",
        ],
        visible_text=(
            "Great Snack for the whole family\nBAMBA\nPEANUT BUTTER PUFFS\nBANANA\n"
            "NATURALLY FLAVORED WITH OTHER NATURAL FLAVORS\nNON GMO\nProtein"
        ),
        image_type="photo",
    ),
    "IMG_2451.jpg": Metadata(
        title="Trader Joe's Bamba on a shop shelf",
        description=(
            "White and orange bags of Trader Joe's Bamba puffed peanut and corn snacks, "
            "decorated with a hot-air balloon, stand on a supermarket shelf next to a brown "
            "hazelnut-cream variety. A handwritten price label is on the shelf edge."
        ),
        tags=[
            "snack",
            "bamba",
            "trader joe's",
            "peanut",
            "corn",
            "puffs",
            "bag",
            "shelf",
            "supermarket",
            "grocery",
            "hot air balloon",
            "hazelnut",
            "food",
        ],
        visible_text=(
            "TRADER JOE'S BAMBA puffed peanut & corn snacks NET WT. 3.5 OZ (100g)\n"
            "BAMBA HAZELNUT CREAM"
        ),
        image_type="photo",
    ),
    "Screenshot_0714.jpg": Metadata(
        title="Subway directions from 34 St-Penn Station",
        description=(
            "A phone screenshot of transit directions: a 22-minute trip costing $3, taking the "
            "E train two stops from 34 St-Penn Station to 14 St / 8 Av, a 3-minute walk, then "
            "the L train toward Canarsie-Rockaway Pkwy."
        ),
        tags=[
            "subway",
            "directions",
            "transit",
            "train",
            "route",
            "map",
            "phone",
            "new york",
            "penn station",
            "fare",
            "e train",
            "l train",
            "commute",
        ],
        visible_text=(
            "22 min\nArrive 16:47 · $3\nA C E > L > 6 > 6\n34 St-Penn Station 16:26\n"
            "Follow signs for Downtown & Brooklyn Local C E\nE World Trade Center\nEvery 2 min\n"
            "What's it like on board?\nAccessible\nNot too crowded\nStation notice\n"
            "Ride 2 stops (4 min)\n14 St / 8 Av\nWalk 3 min\n"
            "Follow signs for East Side & Brooklyn\nCanarsie-Rockaway Pkwy\nSaved\nReport delay"
        ),
        image_type="screenshot",
    ),
    # --- text files ----------------------------------------------------------
    "london_week.md": Metadata(
        title="London week, August 2026",
        description=(
            "A travel diary of a week in London: Big Ben and Westminster traffic, a walk along "
            "the Thames to Tower Bridge, elderflower cocktails in a Greenwich bar, and rides on "
            "the Underground from Tottenham Court Road."
        ),
        tags=[
            "london",
            "travel diary",
            "big ben",
            "westminster",
            "tower bridge",
            "thames",
            "greenwich",
            "cocktails",
            "underground",
            "tottenham court road",
            "august 2026",
        ],
        visible_text="",
        image_type=None,
    ),
    "marseille_and_rome.md": Metadata(
        title="Marseille and Rome, August 2026",
        description=(
            "Travel notes from Marseille and Rome: a walk up to the harbour fort and its "
            "watchtower, flower-shaped gelato, an early flight from Nice with an El Al plane at "
            "the next gate, and the crowded square in front of the Pantheon."
        ),
        tags=[
            "marseille",
            "rome",
            "travel notes",
            "fort",
            "gelato",
            "flight",
            "nice",
            "el al",
            "pantheon",
            "italy",
            "france",
            "august 2026",
        ],
        visible_text="",
        image_type=None,
    ),
    "monday_notes.txt": Metadata(
        title="Notes for Monday",
        description=(
            "A to-do note for the week: the quarterly report waits on a signed supplier "
            "contract and scanned lease amendment pages before being merged into one PDF for "
            "sign-off, and the insurance claim forms need photographing before posting."
        ),
        tags=[
            "work",
            "notes",
            "quarterly report",
            "contract",
            "lease amendment",
            "pdf",
            "insurance claim",
            "forms",
            "paperwork",
            "to-do",
        ],
        visible_text="",
        image_type=None,
    ),
    "new_york_notes.md": Metadata(
        title="New York notes, spring and summer 2026",
        description=(
            "Notes from New York: a $3 subway ride from 34 St-Penn Station, the clock tower in "
            "Madison Square Park lit up at night, and the Warhol soup cans at MoMA."
        ),
        tags=[
            "new york",
            "subway",
            "penn station",
            "fare",
            "madison square park",
            "clock tower",
            "night",
            "moma",
            "warhol",
            "museum",
            "2026",
        ],
        visible_text="",
        image_type=None,
    ),
    "packing_list.txt": Metadata(
        title="Packing list for Europe, August",
        description=(
            "A packing checklist for a European trip: bags, passports and travel documents, "
            "UK and EU plug adapters and a power bank, clothes, and jobs before leaving the "
            "flat, including leaving the spare car key on the umbrella hook."
        ),
        tags=[
            "packing list",
            "travel",
            "europe",
            "checklist",
            "passports",
            "plug adapters",
            "electronics",
            "power bank",
            "clothes",
            "car key",
            "flat",
        ],
        visible_text="",
        image_type=None,
    ),
    "portrait_notes.md": Metadata(
        title="Portraits I want to remember",
        description=(
            "Notes on three portraits seen in a gallery on a rainy afternoon: a young woman in "
            "a green dress with dark hair pulled tight, two young brothers with a bored dog, "
            "and an old sailor with a white beard."
        ),
        tags=[
            "portraits",
            "paintings",
            "gallery",
            "art",
            "notes",
            "woman",
            "brothers",
            "dog",
            "sailor",
            "harbourmaster",
        ],
        visible_text="",
        image_type=None,
    ),
    "salon_appointment.txt": Metadata(
        title="Hair salon appointment",
        description=(
            "Notes for a Tuesday hair salon appointment: keep the black hair as it is with "
            "only a trim, ask about covering grey at the temples, and book the next visit for "
            "October."
        ),
        tags=[
            "hair salon",
            "appointment",
            "haircut",
            "trim",
            "black hair",
            "grey hair",
            "tuesday",
            "reminder",
        ],
        visible_text="",
        image_type=None,
    ),
    "travel_documents.md": Metadata(
        title="Travel documents: what to keep",
        description=(
            "A checklist of travel documents to keep after a trip: passport copy, travel "
            "insurance policy and claim form, hotel registration form, receipts for the VAT "
            "refund, and transport confirmations; plus what to throw away."
        ),
        tags=[
            "travel documents",
            "checklist",
            "passport",
            "travel insurance",
            "hotel",
            "receipts",
            "vat refund",
            "boarding passes",
            "paperwork",
        ],
        visible_text="",
        image_type=None,
    ),
    "white_mountains_journal.md": Metadata(
        title="White Mountains journal, July 2026",
        description=(
            "A two-day journal from New Hampshire's White Mountains: the auto road to the "
            "summit with a red Corvette in the car park and hazy ridges below, waterfalls on "
            "the Kancamagus, and a long loop trail that ended with falling asleep in boots."
        ),
        tags=[
            "white mountains",
            "new hampshire",
            "journal",
            "hiking",
            "summit",
            "corvette",
            "waterfalls",
            "kancamagus",
            "trail",
            "cabin",
            "july 2026",
        ],
        visible_text="",
        image_type=None,
    ),
    "work_todo.txt": Metadata(
        title="Work to-do before time off",
        description=(
            "A checklist of work tasks before a holiday: rotating staging API keys, handing "
            "over on-call, finishing the bridge between the billing service and the new "
            "ledger, documenting deployment steps and cancelling meetings."
        ),
        tags=[
            "work",
            "to-do",
            "checklist",
            "api keys",
            "staging",
            "on-call",
            "billing",
            "ledger",
            "deployment",
            "wiki",
            "time off",
        ],
        visible_text="",
        image_type=None,
    ),
}
