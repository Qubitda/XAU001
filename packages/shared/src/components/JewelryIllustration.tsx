import { JewelryVisualType, MetalColor, StoneType } from '../types/jewelry';
import { formatTrNumber } from '../utils/pricingEngine';

interface JewelryIllustrationProps {
  visualType: JewelryVisualType;
  metalColor: MetalColor;
  stoneType: StoneType;
  centerStoneCarat: number;
  sideStoneCarat: number;
  angle?: number;
  showDimensions?: boolean;
  widthMm?: number;
  thicknessMm?: number;
  heightMm?: number;
  title?: string;
  className?: string;
}

const METAL_PALETTES: Record<
  MetalColor,
  {
    light: string;
    mid: string;
    dark: string;
    highlight: string;
    stroke: string;
  }
> = {
  Beyaz: {
    light: '#F4F5F7',
    mid: '#D2D7E0',
    dark: '#798190',
    highlight: '#FFFFFF',
    stroke: '#949CAE',
  },
  Sarı: {
    light: '#F8E8B8',
    mid: '#D4AC52',
    dark: '#85621E',
    highlight: '#FFF9E2',
    stroke: '#9E792C',
  },
  Rose: {
    light: '#F5D6CA',
    mid: '#CF8E77',
    dark: '#834A38',
    highlight: '#FFF0EA',
    stroke: '#9B5D4A',
  },
};

function getGemColors(stoneType: StoneType) {
  if (stoneType === 'Zümrüt') {
    return { crown: '#10B981', pavilion: '#065F46', table: '#6EE7B7', stroke: '#064E3B' };
  }
  if (stoneType === 'Safir') {
    return { crown: '#2563EB', pavilion: '#1E3A8A', table: '#93C5FD', stroke: '#1E3A8A' };
  }
  if (stoneType === 'Yakut') {
    return { crown: '#E11D48', pavilion: '#881337', table: '#FDA4AF', stroke: '#881337' };
  }
  return { crown: '#F1F5F9', pavilion: '#CBD5E1', table: '#FFFFFF', stroke: '#64748B' };
}

export function JewelryIllustration({
  visualType,
  metalColor,
  stoneType,
  centerStoneCarat,
  sideStoneCarat,
  angle = 18,
  showDimensions = false,
  widthMm = 2.2,
  thicknessMm = 1.6,
  heightMm = 6.5,
  title = 'Mücevher görseli',
  className = 'w-full max-w-[320px] h-auto select-none',
}: JewelryIllustrationProps) {
  const palette = METAL_PALETTES[metalColor];
  const gem = getGemColors(stoneType);
  const uid = `${visualType}-${metalColor}`.replace(/\s+/g, '');

  const tiltRad = ((angle - 18) * Math.PI) / 180;
  const shiftX = Math.sin(tiltRad) * 14;
  const diamondScale = Math.min(1.22, Math.max(0.78, 0.72 + centerStoneCarat * 0.52));
  const bandRx = 82 - Math.abs(Math.sin(tiltRad)) * 16;

  return (
    <svg viewBox="0 0 360 280" className={className} role="img" aria-label={title}>
      <defs>
        <linearGradient id={`metalGrad-${uid}`} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor={palette.highlight} />
          <stop offset="28%" stopColor={palette.light} />
          <stop offset="58%" stopColor={palette.mid} />
          <stop offset="84%" stopColor={palette.dark} />
          <stop offset="100%" stopColor={palette.light} />
        </linearGradient>
        <linearGradient id={`metalInner-${uid}`} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor={palette.dark} />
          <stop offset="50%" stopColor={palette.mid} />
          <stop offset="100%" stopColor={palette.highlight} />
        </linearGradient>
        <linearGradient id={`diamondCrown-${uid}`} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#FFFFFF" />
          <stop offset="40%" stopColor={gem.crown} />
          <stop offset="100%" stopColor={gem.pavilion} />
        </linearGradient>
        <radialGradient id={`shadow-${uid}`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="rgba(17,19,24,0.16)" />
          <stop offset="70%" stopColor="rgba(17,19,24,0.04)" />
          <stop offset="100%" stopColor="rgba(17,19,24,0)" />
        </radialGradient>
      </defs>

      {/* Studio floor shadow */}
      <ellipse cx="180" cy="248" rx="92" ry="13" fill={`url(#shadow-${uid})`} />

      {/* 1. SOLITAIRE RING */}
      {visualType === 'solitaire_ring' && (
        <g>
          <ellipse
            cx="180"
            cy="170"
            rx={bandRx}
            ry="64"
            fill="none"
            stroke={`url(#metalInner-${uid})`}
            strokeWidth="10"
            opacity="0.72"
          />
          <ellipse
            cx="180"
            cy="172"
            rx={bandRx + 2}
            ry="66"
            fill="none"
            stroke={`url(#metalGrad-${uid})`}
            strokeWidth="14"
          />
          <ellipse
            cx="180"
            cy="172"
            rx={bandRx + 7}
            ry="71"
            fill="none"
            stroke={palette.highlight}
            strokeWidth="1.1"
            opacity="0.75"
          />
          {sideStoneCarat > 0 && stoneType !== 'Taşsız' && (
            <g>
              {[-46, -34, -22, 22, 34, 46].map((dx, idx) => (
                <g
                  key={idx}
                  transform={`translate(${180 + dx + shiftX * 0.35}, ${109 + Math.abs(dx) * 0.33})`}
                >
                  <polygon
                    points="0,-4.2 4,0 0,4.2 -4,0"
                    fill="#FFFFFF"
                    stroke="#94A3B8"
                    strokeWidth="0.65"
                  />
                </g>
              ))}
            </g>
          )}
          <g transform={`translate(${180 + shiftX * 0.45}, 102)`}>
            <path
              d="M -21 13 L -13 -15 L 13 -15 L 21 13 Z"
              fill={`url(#metalGrad-${uid})`}
              stroke={palette.stroke}
              strokeWidth="0.9"
            />
            {stoneType !== 'Taşsız' && (
              <g transform={`translate(0, -23) scale(${diamondScale})`}>
                <polygon
                  points="-33,0 33,0 0,33"
                  fill={gem.pavilion}
                  stroke={gem.stroke}
                  strokeWidth="0.8"
                />
                <polygon
                  points="-33,0 -19,-14 19,-14 33,0"
                  fill={`url(#diamondCrown-${uid})`}
                  stroke={gem.stroke}
                  strokeWidth="0.8"
                />
                <polygon points="-19,-14 19,-14 11,0 -11,0" fill={gem.table} opacity="0.82" />
                <line x1="-11" y1="0" x2="0" y2="33" stroke={gem.stroke} strokeWidth="0.65" opacity="0.6" />
                <line x1="11" y1="0" x2="0" y2="33" stroke={gem.stroke} strokeWidth="0.65" opacity="0.6" />
                <polygon points="-13,-10 5,-10 -2,-3" fill="#FFFFFF" opacity="0.9" />
              </g>
            )}
            <path
              d="M -26 -23 C -28 -11, -22 4, -17 13"
              fill="none"
              stroke={`url(#metalGrad-${uid})`}
              strokeWidth="4.2"
              strokeLinecap="round"
            />
            <path
              d="M 26 -23 C 28 -11, 22 4, 17 13"
              fill="none"
              stroke={`url(#metalGrad-${uid})`}
              strokeWidth="4.2"
              strokeLinecap="round"
            />
            <circle cx="-26" cy="-24" r="2.8" fill={palette.highlight} stroke={palette.stroke} strokeWidth="0.7" />
            <circle cx="26" cy="-24" r="2.8" fill={palette.highlight} stroke={palette.stroke} strokeWidth="0.7" />
          </g>
        </g>
      )}

      {/* 2. BAGUETTE HALO RING */}
      {visualType === 'baguette_ring' && (
        <g>
          <ellipse
            cx="180"
            cy="172"
            rx={bandRx}
            ry="64"
            fill="none"
            stroke={`url(#metalGrad-${uid})`}
            strokeWidth="13"
          />
          <ellipse
            cx="180"
            cy="172"
            rx={bandRx + 5}
            ry="69"
            fill="none"
            stroke={palette.highlight}
            strokeWidth="1"
            opacity="0.7"
          />
          <g transform={`translate(${180 + shiftX * 0.45}, 96)`}>
            {/* Halo frame */}
            <rect
              x="-42"
              y="-30"
              width="84"
              height="48"
              rx="8"
              fill={`url(#metalGrad-${uid})`}
              stroke={palette.stroke}
              strokeWidth="1.2"
            />
            {/* Halo micro stones */}
            {[-34, -22, -10, 2, 14, 26, 34].map((x, i) => (
              <g key={i}>
                <circle cx={x} cy="-23" r="2.6" fill="#FFFFFF" stroke="#94A3B8" strokeWidth="0.6" />
                <circle cx={x} cy="11" r="2.6" fill="#FFFFFF" stroke="#94A3B8" strokeWidth="0.6" />
              </g>
            ))}
            {/* Step-cut center baguette cluster */}
            <rect
              x="-26"
              y="-17"
              width="52"
              height="22"
              rx="2"
              fill={`url(#diamondCrown-${uid})`}
              stroke={gem.stroke}
              strokeWidth="0.9"
            />
            <rect x="-18" y="-12" width="36" height="12" fill={gem.table} stroke="#94A3B8" strokeWidth="0.6" />
            <line x1="-26" y1="-17" x2="-18" y2="-12" stroke="#94A3B8" strokeWidth="0.6" />
            <line x1="26" y1="-17" x2="18" y2="-12" stroke="#94A3B8" strokeWidth="0.6" />
            <line x1="-26" y1="5" x2="-18" y2="0" stroke="#94A3B8" strokeWidth="0.6" />
            <line x1="26" y1="5" x2="18" y2="0" stroke="#94A3B8" strokeWidth="0.6" />
          </g>
        </g>
      )}

      {/* 3. SOLITAIRE PENDANT NECKLACE */}
      {visualType === 'pendant_necklace' && (
        <g>
          {/* Fine Forse chain */}
          <path
            d={`M 70 30 Q ${180 + shiftX * 0.4} 210, 290 30`}
            fill="none"
            stroke={`url(#metalGrad-${uid})`}
            strokeWidth="2.8"
          />
          <path
            d={`M 70 30 Q ${180 + shiftX * 0.4} 210, 290 30`}
            fill="none"
            stroke={palette.dark}
            strokeWidth="1"
            strokeDasharray="3 4"
            opacity="0.55"
          />
          {/* Bail */}
          <g transform={`translate(${180 + shiftX * 0.35}, 122)`}>
            <ellipse
              cx="0"
              cy="0"
              rx="7"
              ry="13"
              fill="none"
              stroke={`url(#metalGrad-${uid})`}
              strokeWidth="4.2"
            />
            {/* Pendant bezel & brilliant solitaire */}
            <circle
              cx="0"
              cy="32"
              r={26 * diamondScale * 0.9}
              fill={`url(#metalGrad-${uid})`}
              stroke={palette.stroke}
              strokeWidth="1.2"
            />
            <polygon
              points="0,12 20,24 14,48 -14,48 -20,24"
              fill={`url(#diamondCrown-${uid})`}
              stroke={gem.stroke}
              strokeWidth="0.8"
            />
            <polygon points="0,18 12,26 8,40 -8,40 -12,26" fill={gem.table} opacity="0.88" />
            <line x1="0" y1="12" x2="0" y2="18" stroke="#94A3B8" strokeWidth="0.7" />
            <line x1="20" y1="24" x2="12" y2="26" stroke="#94A3B8" strokeWidth="0.7" />
            <line x1="-20" y1="24" x2="-12" y2="26" stroke="#94A3B8" strokeWidth="0.7" />
            <line x1="14" y1="48" x2="8" y2="40" stroke="#94A3B8" strokeWidth="0.7" />
            <line x1="-14" y1="48" x2="-8" y2="40" stroke="#94A3B8" strokeWidth="0.7" />
            <circle cx="-18" cy="18" r="2.6" fill={palette.highlight} stroke={palette.stroke} strokeWidth="0.7" />
            <circle cx="18" cy="18" r="2.6" fill={palette.highlight} stroke={palette.stroke} strokeWidth="0.7" />
            <circle cx="-16" cy="46" r="2.6" fill={palette.highlight} stroke={palette.stroke} strokeWidth="0.7" />
            <circle cx="16" cy="46" r="2.6" fill={palette.highlight} stroke={palette.stroke} strokeWidth="0.7" />
          </g>
        </g>
      )}

      {/* 4. DIAMOND TENNIS BRACELET */}
      {visualType === 'tennis_bracelet' && (
        <g transform={`translate(${shiftX * 0.35}, 0)`}>
          <ellipse
            cx="180"
            cy="146"
            rx="112"
            ry="52"
            fill="none"
            stroke={`url(#metalGrad-${uid})`}
            strokeWidth="12"
          />
          {/* Continuous diamond stones along front arc */}
          {Array.from({ length: 15 }).map((_, i) => {
            const t = (i / 14) * Math.PI;
            const cx = 180 - Math.cos(t) * 112;
            const cy = 146 + Math.sin(t) * 52;
            return (
              <g key={i} transform={`translate(${cx}, ${cy})`}>
                <rect
                  x="-6.5"
                  y="-6.5"
                  width="13"
                  height="13"
                  rx="2.5"
                  fill={`url(#metalGrad-${uid})`}
                  stroke={palette.stroke}
                  strokeWidth="0.8"
                />
                <polygon
                  points="0,-5 5,0 0,5 -5,0"
                  fill="#FFFFFF"
                  stroke="#94A3B8"
                  strokeWidth="0.65"
                />
              </g>
            );
          })}
          {/* Clasp accent at top back */}
          <rect
            x="166"
            y="88"
            width="28"
            height="12"
            rx="3"
            fill={`url(#metalGrad-${uid})`}
            stroke={palette.stroke}
            strokeWidth="1"
          />
        </g>
      )}

      {/* 5. EMERALD & DIAMOND HALO EARRINGS */}
      {visualType === 'emerald_earring' && (
        <g transform={`translate(${shiftX * 0.35}, 0)`}>
          {[-56, 56].map((offsetX, pairIdx) => (
            <g key={pairIdx} transform={`translate(${180 + offsetX}, 136)`}>
              {/* Top stud post */}
              <circle
                cx="0"
                cy="-44"
                r="10"
                fill={`url(#metalGrad-${uid})`}
                stroke={palette.stroke}
                strokeWidth="1"
              />
              <polygon points="0,-50 6,-44 0,-38 -6,-44" fill="#FFFFFF" stroke="#94A3B8" strokeWidth="0.6" />
              {/* Link */}
              <line x1="0" y1="-34" x2="0" y2="-22" stroke={palette.mid} strokeWidth="2.5" />
              {/* Oval Halo drop */}
              <ellipse
                cx="0"
                cy="12"
                rx="30"
                ry="38"
                fill={`url(#metalGrad-${uid})`}
                stroke={palette.stroke}
                strokeWidth="1.1"
              />
              {/* Halo micro diamonds */}
              {Array.from({ length: 12 }).map((_, j) => {
                const a = (j / 12) * Math.PI * 2;
                return (
                  <circle
                    key={j}
                    cx={Math.cos(a) * 23}
                    cy={12 + Math.sin(a) * 31}
                    r="2.7"
                    fill="#FFFFFF"
                    stroke="#94A3B8"
                    strokeWidth="0.55"
                  />
                );
              })}
              {/* Center Emerald / Gemstone */}
              <ellipse
                cx="0"
                cy="12"
                rx="16"
                ry="23"
                fill={gem.crown}
                stroke={gem.stroke}
                strokeWidth="1"
              />
              <ellipse cx="-3" cy="6" rx="8" ry="12" fill={gem.table} opacity="0.55" />
            </g>
          ))}
        </g>
      )}

      {/* 6. ETERNITY BAND RING (TAMTUR ALYANS) */}
      {visualType === 'eternity_ring' && (
        <g transform={`translate(${shiftX * 0.35}, 0)`}>
          <ellipse
            cx="180"
            cy="154"
            rx={bandRx + 4}
            ry="60"
            fill="none"
            stroke={`url(#metalInner-${uid})`}
            strokeWidth="14"
            opacity="0.7"
          />
          <ellipse
            cx="180"
            cy="156"
            rx={bandRx + 6}
            ry="62"
            fill="none"
            stroke={`url(#metalGrad-${uid})`}
            strokeWidth="18"
          />
          {/* Princess-cut channel diamonds around front face */}
          {Array.from({ length: 13 }).map((_, i) => {
            const t = (i / 12) * Math.PI;
            const cx = 180 - Math.cos(t) * (bandRx + 6);
            const cy = 156 + Math.sin(t) * 62;
            return (
              <g key={i} transform={`translate(${cx}, ${cy})`}>
                <rect
                  x="-5.5"
                  y="-5.5"
                  width="11"
                  height="11"
                  fill="#FFFFFF"
                  stroke="#94A3B8"
                  strokeWidth="0.75"
                />
                <line x1="-5.5" y1="-5.5" x2="5.5" y2="5.5" stroke="#CBD5E1" strokeWidth="0.6" />
                <line x1="5.5" y1="-5.5" x2="-5.5" y2="5.5" stroke="#CBD5E1" strokeWidth="0.6" />
              </g>
            );
          })}
        </g>
      )}

      {/* Optional Technical Dimension Callouts (Product Detail Studio) */}
      {showDimensions && (
        <g className="font-mono" fill="#71717A" fontSize="9.5">
          <line x1="292" y1="68" x2="292" y2="128" stroke="#D4D4D8" strokeWidth="1" strokeDasharray="2 2" />
          <text x="298" y="101">
            {formatTrNumber(heightMm, 1)} mm
          </text>
          <line x1="138" y1="236" x2="222" y2="236" stroke="#D4D4D8" strokeWidth="1" strokeDasharray="2 2" />
          <text x="180" y="230" textAnchor="middle">
            Genişlik {formatTrNumber(widthMm, 1)} mm · Kalınlık {formatTrNumber(thicknessMm, 1)} mm
          </text>
        </g>
      )}
    </svg>
  );
}
