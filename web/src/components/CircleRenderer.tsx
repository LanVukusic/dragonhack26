import { Circle, Text } from "react-konva";
import type { CircleData } from "../types/websocket";

interface CircleRendererProps {
  circles: CircleData[];
}

const COLORS: [number, number, number][] = [
  [255, 0, 0], // 0: Red
  [0, 255, 0], // 1: Green
  [0, 0, 255], // 2: Blue
  [255, 255, 0], // 3: Yellow
  [255, 0, 255], // 4: Magenta
  [0, 255, 255], // 5: Cyan
  [255, 128, 0], // 6: Orange
  [128, 0, 255], // 7: Purple
  [0, 128, 128], // 8: Teal
  [128, 128, 0], // 9: Olive
];

const RADIUS = 0.025;
const STROKE_WIDTH = 0.004;
const SHADOW_BLUR = 0.03;
const TEXT_OFFSET_X = RADIUS * 2;
const TEXT_OFFSET_Y = RADIUS;
const FONT_SIZE = 0.015;

function getColor(id: number): string {
  const c = COLORS[id % COLORS.length];
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

export function CircleRenderer({ circles }: CircleRendererProps) {
  const circleElements = circles.map((circle) => {
    const { id, x, y, in_frame } = circle;
    const color = getColor(id);
    const opacity = in_frame !== false ? 1 : 0.3;

    return (
      <Circle
        key={id}
        x={x}
        y={y}
        radius={RADIUS}
        fill={color}
        strokeWidth={STROKE_WIDTH}
        stroke={color}
        shadowColor={color}
        shadowBlur={SHADOW_BLUR}
        shadowEnabled={in_frame !== false}
        shadowOpacity={1}
        opacity={opacity}
      />
    );
  });

  const textElements = circles.map((circle) => {
    const { id, x, y, in_frame } = circle;
    const status = in_frame !== false ? "IN" : "OUT";
    const label = `ID: ${id}\n(${x.toFixed(3)}, ${y.toFixed(3)})\n${status}`;

    return (
      <Text
        key={`text-${id}`}
        x={x + TEXT_OFFSET_X}
        y={y - TEXT_OFFSET_Y}
        text={label}
        fontSize={FONT_SIZE}
        fill="#333"
        fontStyle="bold"
      />
    );
  });

  return (
    <>
      {circleElements}
      {textElements}
    </>
  );
}
