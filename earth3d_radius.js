"use strict"
// ============================================================
//  earth3d_radius.js -- octants couvrant un disque de rayon R
//  (en metres) autour d'un point (lat, lng).
//
//  Copie automatiquement dans earth3d_vendor/exporter/ par
//  earth3d.py (necessite les lib/ de l'exporter retroplasma).
//
//  Usage : node earth3d_radius.js <lat> <lng> <rayon_m> [max_octants]
//  Sortie machine (stdout) :
//      LEVEL <niveau>
//      CELL_M <taille de cellule en metres>
//      OCT <path>        (une ligne par octant)
//  Les messages humains vont sur stderr.
// ============================================================

const M_PER_DEG = 111320;

// Les 8 racines du quadtree lat/lng (cf. lib/convert-lat-long-to-octant.js)
const ROOTS = [
	['02', { n: 0, s: -90, w: -180, e: -90 }],
	['03', { n: 0, s: -90, w: -90, e: 0 }],
	['12', { n: 0, s: -90, w: 0, e: 90 }],
	['13', { n: 0, s: -90, w: 90, e: 180 }],
	['20', { n: 90, s: 0, w: -180, e: -90 }],
	['21', { n: 90, s: 0, w: -90, e: 0 }],
	['30', { n: 90, s: 0, w: 0, e: 90 }],
	['31', { n: 90, s: 0, w: 90, e: 180 }],
];

// Reproduit getNextOctant pour LES 4 quadrants (au lieu du seul quadrant
// contenant le point). Cas particulier des poles : pas de split en longitude.
function children(box) {
	const { n, s, w, e } = box;
	const mid_lat = (n + s) / 2, mid_lon = (w + e) / 2;
	const out = [];
	for (const y of [0, 1]) {
		const cb = y ? { n: n, s: mid_lat, w: w, e: e }
		             : { n: mid_lat, s: s, w: w, e: e };
		if (cb.n === 90 || cb.s === -90) {
			out.push([y * 2, cb]);
		} else {
			out.push([y * 2,     { n: cb.n, s: cb.s, w: w, e: mid_lon }]);
			out.push([y * 2 + 1, { n: cb.n, s: cb.s, w: mid_lon, e: e }]);
		}
	}
	return out;
}

// Le disque de rayon r (m) autour de (lat,lng) touche-t-il la box ?
// Approximation equirectangulaire locale, suffisante a ces echelles.
function discIntersects(box, lat, lng, r) {
	const clat = Math.min(Math.max(lat, box.s), box.n);
	const clng = Math.min(Math.max(lng, box.w), box.e);
	const dy = (clat - lat) * M_PER_DEG;
	const dx = (clng - lng) * M_PER_DEG * Math.cos(lat * Math.PI / 180);
	return dx * dx + dy * dy <= r * r;
}

function cellSizeM(box) { return (box.n - box.s) * M_PER_DEG; }

module.exports = { children, discIntersects, cellSizeM, ROOTS };

/***************************** main *****************************/

async function main() {
	const [lat, lng, radius] = process.argv.slice(2, 5).map(parseFloat);
	const maxOct = parseInt(process.argv[5]) || 96;
	const HARD_MAX_LEVEL = 20;

	if ([lat, lng, radius].some(isNaN)) {
		console.error('Usage: node earth3d_radius.js <lat> <lng> <rayon_m> [max_octants]');
		process.exit(1);
	}

	const PLANET = 'earth';
	const URL_PREFIX = `https://kh.google.com/rt/${PLANET}/`;
	const utils = require('./lib/utils')({
		URL_PREFIX, DUMP_JSON_DIR: null, DUMP_RAW_DIR: null,
		DUMP_JSON: false, DUMP_RAW: false
	});
	const { getPlanetoid, getBulk,
	        bulk: { getIndexByPath, hasBulkMetadataAtIndex } } = utils;

	const planetoid = await getPlanetoid();
	const rootEpoch = planetoid.bulkMetadataEpoch[0];

	// Copie de lib/convert-lat-long-to-octant.js (checkNodePath)
	async function checkNodePath(nodePath) {
		let bulk = null, index = -1;
		for (let epoch = rootEpoch, i = 4; i < nodePath.length + 4; i += 4) {
			const bulkPath = nodePath.substring(0, i - 4);
			const subPath = nodePath.substring(0, i);
			if (bulk) {
				const idx = getIndexByPath(bulk, bulkPath);
				if (hasBulkMetadataAtIndex(bulk, idx)) return false;
			}
			const nextBulk = await getBulk(bulkPath, epoch);
			bulk = nextBulk;
			index = getIndexByPath(bulk, subPath);
			epoch = bulk.bulkMetadataEpoch[index];
		}
		return (index >= 0);
	}

	// BFS : a chaque niveau, garder les octants existants dont la box
	// intersecte le disque. S'arreter quand plus rien n'existe, que le
	// niveau max est atteint, ou que le nombre d'octants depasse maxOct.
	let current = [];
	for (const [p, b] of ROOTS) {
		if (!discIntersects(b, lat, lng, radius)) continue;
		try { if (await checkNodePath(p)) current.push([p, b]); }
		catch (ex) { /* racine indisponible */ }
	}
	if (!current.length) {
		console.error('Aucune donnee 3D ici (racines vides).');
		process.exit(2);
	}

	while (current[0][0].length < HARD_MAX_LEVEL) {
		const next = [];
		let overflow = false;
		for (const [p, b] of current) {
			for (const [k, cb] of children(b)) {
				if (!discIntersects(cb, lat, lng, radius)) continue;
				for (const key of [k, k + 4]) {
					const np = p + key;
					try {
						if (await checkNodePath(np)) next.push([np, cb]);
					} catch (ex) { /* branche indisponible */ }
					if (next.length > maxOct) { overflow = true; break; }
				}
				if (overflow) break;
			}
			if (overflow) break;
		}
		if (overflow) {
			console.error(`Niveau ${current[0][0].length + 1} : > ${maxOct} octants, ` +
			              `on s'arrete au niveau ${current[0][0].length} ` +
			              `(meme detail final, selection un peu plus large).`);
			break;
		}
		if (!next.length) break;
		current = next;
		console.error(`Niveau ${current[0][0].length} : ${current.length} octant(s)`);
	}

	console.log('LEVEL ' + current[0][0].length);
	console.log('CELL_M ' + Math.round(cellSizeM(current[0][1])));
	for (const [p] of current) console.log('OCT ' + p);
}

if (require.main === module) {
	main().then(() => process.exit(0)).catch(e => {
		console.error(e);
		process.exit(1);
	});
}
