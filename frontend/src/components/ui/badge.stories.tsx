import type { Meta, StoryObj } from "@storybook/nextjs-vite"

import { Badge } from "./badge"

const meta = {
  title: "UI/Badge",
  component: Badge,
  args: {
    children: "Connected",
  },
} satisfies Meta<typeof Badge>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const Outline: Story = {
  args: {
    variant: "outline",
  },
}

export const Destructive: Story = {
  args: {
    variant: "destructive",
    children: "Needs attention",
  },
}
