// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
expect.extend(matchers);

import { CalendarSidebarRight } from './CalendarSidebarRight';

describe('CalendarSidebarRight', () => {
  it('renders default text when selectedDetailEvent is null', () => {
    render(<CalendarSidebarRight selectedDetailEvent={null} />);

    // Title
    expect(screen.getByText('표시 중인 일정 없음')).toBeInTheDocument();

    // Description
    expect(screen.getByText('왼쪽 캘린더 목록에서 하나 이상의 캘린더를 표시하세요.')).toBeInTheDocument();

    // Empty Location Button
    const locationBtn = screen.getByRole('button', { name: '장소 위치 보기' });
    expect(locationBtn).toBeInTheDocument();

    // Default aria labels for action buttons
    expect(screen.getByRole('button', { name: '선택한 일정 삭제' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '선택한 일정 복사' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '선택한 일정 수정' })).toBeInTheDocument();
  });

  it('renders correctly with selectedDetailEvent data', () => {
    const mockEvent = {
      id: '1',
      title: '디자인 리뷰',
      time: '14:00',
      duration: '1시간',
      location: '회의실 A',
      description: '새로운 시안 검토',
      badgeLabel: '중요',
      badgeClassName: 'bg-red-500',
      dotClassName: 'bg-red-500',
    };

    render(<CalendarSidebarRight selectedDetailEvent={mockEvent} />);

    // Title
    expect(screen.getByText('디자인 리뷰 (Naruon 2.0)')).toBeInTheDocument();

    // Description - Use getAllByText because it appears multiple times (under Title and under CalendarDays icon)
    const descriptions = screen.getAllByText('새로운 시안 검토');
    expect(descriptions.length).toBeGreaterThan(0);
    expect(descriptions[0]).toBeInTheDocument();

    // Time
    expect(screen.getByText((content) => content.includes('14:00'))).toBeInTheDocument();
    expect(screen.getByText('1시간')).toBeInTheDocument();

    // Location
    expect(screen.getByText('회의실 A')).toBeInTheDocument();

    // Location Button
    const locationBtn = screen.getByRole('button', { name: '회의실 A 위치 보기' });
    expect(locationBtn).toBeInTheDocument();

    // Action buttons aria labels should include the title
    expect(screen.getByRole('button', { name: '디자인 리뷰 일정 삭제' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '디자인 리뷰 일정 복사' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '디자인 리뷰 일정 수정' })).toBeInTheDocument();
  });
});
