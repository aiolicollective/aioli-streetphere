"use strict"
// ============================================================
//  earth3d_radius.js -- octants covering a disc of radius R
//  (in metres) around a point (lat, lng).
//
//  Copied automatically into earth3d_vendor/exporter/ by
//  earth3d.py (needs the lib/ of the retroplasma exporter).
//
//  Usage: node earth3d_radius.js <lat> <lng> <radius_m> [max_octants]
//  Machine output (stdout):
//      LEVEL <level>
//      CELL_M <cell size in metres>
//      OCT <path>        (one line per octant)
//  Human-readable messages go to stderr.
// ============================================================

const M_PER_DEG = 111320;

// The 8 roots of the lat/lng quadtree (cf. lib/convert-lat-long-to-octant.js)
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

// Reproduces getNextOctant for ALL 4 quadrants (instead of only the one
// containing the point). Special case at the poles: no longitude split.
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

// Does the disc of radius r (m) around (lat,lng) touch the box?
// Local equirectangular approximation, good enough at these scales.
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
		console.error('Usage: node earth3d_radius.js <lat> <lng> <radius_m> [max_octants]');
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

	// Copy of lib/convert-lat-long-to-octant.js (checkNodePath)
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

	// BFS: at each level, keep the existing octants whose box intersects
	// the disc. Stop when nothing is left, when the max level is reached,
	// or when the number of octants goes over maxOct.
	let current = [];
	for (const [p, b] of ROOTS) {
		if (!discIntersects(b, lat, lng, radius)) continue;
		try { if (await checkNodePath(p)) current.push([p, b]); }
		catch (ex) { /* root unavailable */ }
	}
	if (!current.length) {
		console.error('No 3D data here (empty roots).');
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
					} catch (ex) { /* branch unavailable */ }
					if (next.length > maxOct) { overflow = true; break; }
				}
				if (overflow) break;
			}
			if (overflow) break;
		}
		if (overflow) {
			console.error(`Level ${current[0][0].length + 1}: > ${maxOct} octants, ` +
			              `stopping at level ${current[0][0].length} ` +
			              `(same final detail, slightly wider selection).`);
			break;
		}
		if (!next.length) break;
		current = next;
		console.error(`Level ${current[0][0].length}: ${current.length} octant(s)`);
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
