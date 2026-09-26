// Starting data for the mock backend: a `demo` collection with more than one page of results for
// "note" (so "show more" can be tried) and a small `interview` collection. A reload starts from here.
import type { AssetMetadata } from '../api/types'
import type { StoredAsset } from './store'
// `?raw` and `?inline` are Vite import suffixes: the file's text, and the file as a data: URL.
import lisbonNote from './files/note.txt?raw'
import screenshotDataUrl from './files/screenshot.png?inline'

// Each note: filename, title, body, tags. The description is the body's first sentence.
const DEMO_NOTES: [string, string, string, string[]][] = [
  ['standup-monday.txt', 'Monday standup', 'Standup notes: the upload page is done, search is next. Ana is out on Thursday.', ['note', 'meeting']],
  ['standup-tuesday.txt', 'Tuesday standup', 'Standup notes: search returns results but ranking needs work. No blockers.', ['note', 'meeting']],
  ['grocery-list.txt', 'Grocery list', 'Eggs, rice, lemons, olive oil, coffee beans and a birthday card for Sam.', ['note', 'shopping']],
  ['recipe-shakshuka.txt', 'Shakshuka recipe', 'Soften onions and peppers, add tomatoes and cumin, crack four eggs into the sauce and cover.', ['note', 'recipe', 'cooking']],
  ['recipe-pancakes.txt', 'Pancake recipe', 'Two cups of flour, two eggs, milk until it pours, a pinch of salt; rest the batter ten minutes.', ['note', 'recipe', 'cooking']],
  ['book-quotes.txt', 'Quotes from a novel', 'She had black hair cut short and a laugh that filled the room before she did.', ['note', 'books', 'quotes']],
  ['character-sketch.txt', 'Character sketch', 'The detective is tall, blond, and always forgets his umbrella on the train.', ['note', 'writing']],
  ['receipt-hardware.txt', 'Hardware store receipt', 'Receipt: screws, wall plugs, a spirit level. Total 31.80, paid by card.', ['note', 'receipt', 'document']],
  ['receipt-cafe.txt', 'Cafe receipt', 'Receipt from the corner cafe: two flat whites and a croissant, 9.40.', ['note', 'receipt', 'document']],
  ['gym-plan.txt', 'Gym plan', 'Monday legs, Wednesday back and arms, Friday a long run by the river.', ['note', 'fitness']],
  ['reading-list.txt', 'Reading list', 'Designing Data-Intensive Applications, The Pragmatic Programmer, and a thriller for the beach.', ['note', 'books']],
  ['interview-prep.txt', 'Interview prep', 'Explain the queue, the lease and the reaper; walk through one search from query to snippet.', ['note', 'work']],
  ['packing-list.txt', 'Packing list', 'Passport, charger, rain jacket, walking shoes and the printed booking document.', ['note', 'travel', 'document']],
  ['birthday-ideas.txt', 'Birthday ideas', 'A pottery class, a board game, or dinner at the place with the brown wooden tables.', ['note', 'gifts']],
  ['plant-care.txt', 'Plant care', 'Water the fern twice a week, the cactus once a month, and move the basil to the window.', ['note', 'home']],
  ['car-service.txt', 'Car service', 'Oil change due in March; the front left tyre loses pressure slowly.', ['note', 'car']],
  ['meeting-design.txt', 'Design review notes', 'Design review: keep the collection selector at the top, dim low-scoring results.', ['note', 'meeting', 'work']],
  ['podcast-notes.txt', 'Podcast notes', 'An episode on hybrid search: keyword and vector results merged by reciprocal rank.', ['note', 'search']],
  ['wifi-password-hint.txt', 'Wi-Fi hint', 'The router is behind the bookshelf; the hint is the name of the first cat.', ['note', 'home']],
  ['holiday-dates.txt', 'Holiday dates', 'School holidays start on the twentieth; book the train before prices go up.', ['note', 'travel']],
  ['neighbour-note.txt', 'Note for the neighbour', 'The parcel is on the shelf by the door; the brunette courier said she will come back on Friday.', ['note']],
]

const SCREENSHOT_IMAGES: [string, string, string, string[], string][] = [
  ['screenshot.png', 'Game screen with a shop sign', 'A game screenshot with a health bar and a shop sign reading "SYNKA CO."', ['game', 'screenshot', 'sign'], 'SYNKA CO. HP 87/100'],
  ['synka-shop.png', 'Shop front in a game', 'A shop front in a video game, with a sign and a status bar at the top.', ['game', 'shop', 'screenshot'], 'SYNKA CO.'],
  ['level-two.png', 'Second level of a game', 'The start of a game level, a character standing near a sign.', ['game', 'level', 'screenshot'], 'LEVEL 2'],
]

// Turns the inlined data: URL back into bytes, so the mock can serve and hash the image.
function dataUrlToBlob(dataUrl: string): Blob {
  const [header, base64] = dataUrl.split(',')
  const mime = header.slice('data:'.length, header.indexOf(';'))
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index++) {
    bytes[index] = binary.charCodeAt(index)
  }
  return new Blob([bytes], { type: mime })
}

function textMetadata(title: string, body: string, tags: string[]): AssetMetadata {
  const firstSentence = body.split(/(?<=[.!?])\s/)[0]
  return { title, description: firstSentence, tags, visible_text: null, image_type: null, vision_model: 'mock' }
}

function imageMetadata(title: string, description: string, tags: string[], visibleText: string): AssetMetadata {
  return { title, description, tags, visible_text: visibleText, image_type: 'screenshot', vision_model: 'mock' }
}

// queuedAt 0 means "uploaded long ago", so the status clock reports these as finished.
function textAsset(collection: string, filename: string, body: string, metadata: AssetMetadata, minutesAgo: number): StoredAsset {
  return {
    id: crypto.randomUUID(),
    collection,
    filename,
    aliases: [],
    asset_type: 'text',
    body: new Blob([body], { type: 'text/plain' }),
    created_at: new Date(Date.now() - minutesAgo * 60_000).toISOString(),
    metadata,
    queuedAt: 0,
    retried: false,
  }
}

function imageAsset(collection: string, filename: string, metadata: AssetMetadata, minutesAgo: number): StoredAsset {
  return {
    id: crypto.randomUUID(),
    collection,
    filename,
    aliases: [],
    asset_type: 'image',
    body: dataUrlToBlob(screenshotDataUrl),
    created_at: new Date(Date.now() - minutesAgo * 60_000).toISOString(),
    metadata,
    queuedAt: 0,
    retried: false,
  }
}

export function seedAssets(): StoredAsset[] {
  const assets: StoredAsset[] = []
  let minutesAgo = 1

  const lisbon = textAsset(
    'demo',
    'notes-lisbon.txt',
    lisbonNote,
    textMetadata('Trip notes, Lisbon', 'Notes from a weekend in Lisbon: the apartment, Belem, the castle.', ['note', 'travel notes', 'lisbon']),
    minutesAgo++,
  )
  lisbon.aliases = ['lisbon-trip.txt']
  assets.push(lisbon)

  for (const [filename, title, body, tags] of DEMO_NOTES) {
    assets.push(textAsset('demo', filename, body, textMetadata(title, body, tags), minutesAgo++))
  }
  for (const [filename, title, description, tags, visibleText] of SCREENSHOT_IMAGES) {
    assets.push(imageAsset('demo', filename, imageMetadata(title, description, tags, visibleText), minutesAgo++))
  }

  // The `fail` rule in store.ts reports this one as failed, so Retry can be tried at once.
  const failingBody = 'This file always fails its first pass in the mock backend.'
  assets.push(textAsset('demo', 'will-fail.txt', failingBody, textMetadata('Retried file', failingBody, ['note']), minutesAgo++))

  const questions = 'Questions for the interview: how does dedup handle a race? What happens when Gemini is overloaded?'
  const plan = 'Plan for the interview: show the demo collection, create a new one, upload, search.'
  assets.push(textAsset('interview', 'questions.txt', questions, textMetadata('Interview questions', questions, ['interview']), 1))
  assets.push(textAsset('interview', 'plan.txt', plan, textMetadata('Interview plan', plan, ['interview']), 2))
  const screenshotMetadata = imageMetadata(
    'Game screen with a shop sign',
    'A game screenshot with a health bar and a shop sign reading "SYNKA CO."',
    ['game', 'screenshot', 'sign'],
    'SYNKA CO. HP 87/100',
  )
  assets.push(imageAsset('interview', 'screenshot.png', screenshotMetadata, 3))

  return assets
}
