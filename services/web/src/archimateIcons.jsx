// The ArchiMate 4 icons on the views EA Explorer draws itself (R5.7-V1, a bug: owner, 16 Nov 2026, 22:32: "in the
// diagram of a view we cant see icons on the objects, but they are visible in draw.io. The views should show standard
// icons"). Every notation of eax/notation.py (ELEMENTS and the junction) has its glyph here, drawn in our own SVG
// after the ArchiMate standard's icons (the same ones draw.io shows in a box's corner), and the box's corners: square,
// rounded (behaviour and strategy) or cut (motivation). An element with no notation (our extensions, a type without
// an ArchiMate element) gets no glyph and a plain rounded box, as in draw.io. tests/test_r5_7_view_icons.py keeps this
// list and eax/notation.py the same.

// each glyph: SVG parts in a 16 x 16 box, stroked in the text colour; [tag, attributes]
const L = (d, extra = {}) => ["path", { d, ...extra }];
const C = (cx, cy, r, extra = {}) => ["circle", { cx, cy, r, ...extra }];
const R = (x, y, width, height, rx = 0) => ["rect", { x, y, width, height, rx }];
const DOT = { fill: "currentColor", stroke: "none" };
const ROLE = [L("M4,4 H11 A3,4 0 0 1 11,12 H4"), ["ellipse", { cx: 4, cy: 8, rx: 2, ry: 4 }]];
const INTERFACE = [C(11, 8, 3.5), L("M1,8 H7.5")];
const OBJECT = [R(2, 3, 12, 10), L("M2,6 H14")];

export const GLYPHS = {
  BusinessActor: [C(8, 3.5, 2.5), L("M8,6 V11 M4,8 H12 M8,11 L5,15 M8,11 L11,15")],
  Role: ROLE,
  Stakeholder: ROLE,
  Collaboration: [C(6, 8, 4), C(10, 8, 4)],
  BusinessInterface: INTERFACE,
  ApplicationInterface: INTERFACE,
  TechnologyInterface: INTERFACE,
  Process: [L("M1,6 H9 V3 L15,8 L9,13 V10 H1 Z")],
  Function: [L("M3,15 V5 L8,1 L13,5 V15 L8,11 Z")],
  Event: [L("M1,4 H11 A4,4 0 0 1 11,12 H1 L4,8 Z")],
  Service: [R(1, 4, 14, 8, 4)],
  BusinessObject: OBJECT,
  DataObject: OBJECT,
  Product: [R(2, 3, 12, 10), R(2, 3, 6, 3)],
  ApplicationComponent: [R(4, 2, 10, 12), R(2, 4, 4, 2), R(2, 9, 4, 2)],
  Node: [L("M2,5 L5,2 H14 V11 L11,14 H2 Z M2,5 H11 V14 M11,5 L14,2")],
  Device: [R(2, 2, 12, 8, 1), L("M5,14 H11 M8,10 V14")],
  SystemSoftware: [C(7, 9, 5), L("M5,4.5 A5,5 0 1 1 12.5,11.5")],
  CommunicationNetwork: [L("M3,11 L7,4 L13,5 L9,12 Z"), C(3, 11, 1.5, DOT), C(7, 4, 1.5, DOT), C(13, 5, 1.5, DOT), C(9, 12, 1.5, DOT)],
  DistributionNetwork: [L("M1,8 H15 M4,5 L1,8 L4,11 M12,5 L15,8 L12,11")],
  Path: [L("M1,8 H15", { strokeDasharray: "2 2" }), L("M4,5 L1,8 L4,11 M12,5 L15,8 L12,11")],
  Equipment: [C(6, 10, 3.5), C(11, 5, 2.5), L("M6,5.5 V6.5 M6,13.5 V14.5 M1.5,10 H2.5 M9.5,10 H10.5")],
  Facility: [L("M1,15 V7 L5,10 V7 L9,10 V3 H12 V15 Z")],
  Material: [L("M4,2 H12 L15,8 L12,14 H4 L1,8 Z")],
  Artifact: [L("M3,1 H10 L13,4 V15 H3 Z M10,1 V4 H13")],
  Resource: [R(1, 5, 12, 7, 2), R(13, 7, 2, 3), L("M4,7 V10 M7,7 V10 M10,7 V10")],
  Capability: [L("M1,15 H15 V1 H11 V5 H6 V10 H1 Z M6,10 H11 V5 M6,15 V10 M11,15 V10 M11,10 H15")],
  ValueStream: [L("M1,4 H12 L15,8 L12,12 H1 L4,8 Z")],
  CourseOfAction: [C(10, 6, 4.5), C(10, 6, 1.5, DOT), L("M1,15 L7.5,8.5 M1,11 V15 H5")],
  Driver: [C(8, 8, 5.5), C(8, 8, 1.5, DOT), L("M8,1 V15 M1,8 H15 M3,3 L13,13 M13,3 L3,13")],
  Assessment: [C(6.5, 6.5, 4.5), L("M10,10 L15,15")],
  Goal: [C(8, 8, 6.5), C(8, 8, 3.5), C(8, 8, 1, DOT)],
  Outcome: [C(7, 9, 5.5), C(7, 9, 2.8), C(7, 9, 0.9, DOT), L("M7,9 L15,1 M11,1 H15 V5")],
  Principle: [R(3, 1, 10, 14, 1), L("M8,4 V10"), C(8, 12.5, 0.9, DOT)],
  Requirement: [L("M4,4 H15 L12,12 H1 Z")],
  Meaning: [L("M4,12 A3,3 0 0 1 4,6 A4,4 0 0 1 11,5 A3,3 0 0 1 12,12 Z")],
  Value: [["ellipse", { cx: 8, cy: 8, rx: 7, ry: 4 }]],
  WorkPackage: [L("M13,8 A5,5 0 1 1 8,3"), L("M6,1 L8.5,3 L6,5")],
  Deliverable: [L("M2,2 H14 V12 C11,10 6,15 2,12 Z")],
  Plateau: [L("M5,4 H15 M3,8 H13 M1,12 H11", { strokeWidth: 2 })],
  Location: [L("M8,15 C3,9 3,2 8,2 C13,2 13,9 8,15 Z"), C(8, 6.5, 1.8)],
  Grouping: [],                         // a dashed box with no fill, no glyph (as draw.io draws it)
  Junction: [C(8, 8, 4, DOT)],
};

// the corners of a box, by ArchiMate's own families (eax/notation.py's archiType: square, rounded, oct)
const ROUNDED = new Set(["Service", "Process", "Function", "Event", "Capability", "ValueStream", "CourseOfAction", "WorkPackage"]);
const CUT = new Set(["Stakeholder", "Driver", "Assessment", "Goal", "Outcome", "Principle", "Requirement", "Meaning", "Value"]);

export function corners(notation) {
  if (!notation || !(notation in GLYPHS)) return "plain";
  if (ROUNDED.has(notation)) return "rounded";
  if (CUT.has(notation)) return "cut";
  return "square";
}

export const hasGlyph = (notation) => !!notation && (GLYPHS[notation] || []).length > 0;

// the box itself: square, rounded, cut corners, or a plain rounded box (no notation); grouping dashed and unfilled
export function BoxShape({ notation, width, height, fill, stroke, strokeWidth }) {
  const kind = corners(notation);
  const dashed = notation === "Grouping";
  const common = { fill: dashed ? "none" : fill, stroke, strokeWidth, strokeDasharray: dashed ? "6 4" : undefined };
  if (kind === "cut") {
    const c = Math.min(8, height / 4);
    const d = `M${c},0 H${width - c} L${width},${c} V${height - c} L${width - c},${height} H${c} L0,${height - c} V${c} Z`;
    return <path d={d} {...common} />;
  }
  return <rect width={width} height={height} rx={kind === "rounded" ? 10 : kind === "square" ? 1 : 6} {...common} />;
}

// the glyph, `size` pixels square, its top left at x, y; nothing for a notation without one
export function Glyph({ notation, x = 0, y = 0, size = 14, colour = "#1d2733" }) {
  const parts = GLYPHS[notation || ""];
  if (!parts || !parts.length) return null;
  return (
    <g transform={`translate(${x},${y}) scale(${size / 16})`} fill="none" stroke={colour} strokeWidth="1.2"
      strokeLinejoin="round" strokeLinecap="round" color={colour} aria-hidden="true" className="am-glyph">
      {parts.map(([tag, attrs], i) => {
        const T = tag;
        return <T key={i} {...attrs} />;
      })}
    </g>
  );
}
