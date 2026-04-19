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

const SCALE = 1300;

const RADIUS = 0.025 * SCALE;
const STROKE_WIDTH = 0.004 * SCALE;
const SHADOW_BLUR = 0.03 * SCALE;
const TEXT_OFFSET_X = RADIUS * 2 * SCALE;
const TEXT_OFFSET_Y = RADIUS * SCALE;
const FONT_SIZE = 0.015 * SCALE;

function getColor(id: number): string {
  const c = COLORS[id % COLORS.length];
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

export const CircleRenderer = ({ circles }: CircleRendererProps) => {
  const circleElements = circles.map((circle) => {
    const { id, x, y } = circle;
    const color = getColor(id);

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
        shadowEnabled={true}
      />
    );
  });

  const textElements = circles.map((circle) => {
    const { id, x, y } = circle;
    const label = `ID: ${id}\n(${x.toFixed(3)}, ${y.toFixed(3)})`;

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
};
