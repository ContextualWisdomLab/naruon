import type {
  CalendarCandidateEvent,
  CalendarConflictPair,
  CalendarDefinition,
  CalendarMonthEvent,
  CalendarWeekEvent,
} from './types';

const PROPOSED_CONFIRMED_1000Z_ICS = `BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Naruon//Calendar Conflict Fixtures//EN
BEGIN:VEVENT
UID:proposal-confirmed-1000z
DTSTAMP:20260817T000000Z
DTSTART:20260817T100000Z
DTEND:20260817T110000Z
SUMMARY:Confirmed proposal
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR
`;

const PROPOSED_TENTATIVE_1000Z_ICS = `BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Naruon//Calendar Conflict Fixtures//EN
BEGIN:VEVENT
UID:proposal-tentative-1000z
DTSTAMP:20260817T000000Z
DTSTART:20260817T100000Z
DTEND:20260817T110000Z
SUMMARY:Tentative proposal
STATUS:TENTATIVE
END:VEVENT
END:VCALENDAR
`;

const EXISTING_CANCELLED_1000Z_ICS = `BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Naruon//Calendar Conflict Fixtures//EN
BEGIN:VEVENT
UID:existing-cancelled-1000z
DTSTAMP:20260817T000000Z
DTSTART:20260817T100000Z
DTEND:20260817T110000Z
SUMMARY:Cancelled prior booking
STATUS:CANCELLED
END:VEVENT
END:VCALENDAR
`;

const EXISTING_TENTATIVE_1030Z_ICS = `BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Naruon//Calendar Conflict Fixtures//EN
BEGIN:VEVENT
UID:existing-tentative-1030z
DTSTAMP:20260817T000000Z
DTSTART:20260817T103000Z
DTEND:20260817T113000Z
SUMMARY:Tentative hold
STATUS:TENTATIVE
END:VEVENT
END:VCALENDAR
`;

const EXISTING_CONFIRMED_1000Z_ICS = `BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Naruon//Calendar Conflict Fixtures//EN
BEGIN:VEVENT
UID:existing-confirmed-1000z
DTSTAMP:20260817T000000Z
DTSTART:20260817T100000Z
DTEND:20260817T110000Z
SUMMARY:Confirmed prior booking
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR
`;

export const calendarDefinitions: CalendarDefinition[] = [
  { id: 'personal', name: '김나루 (나)', colorClass: 'bg-primary' },
  { id: 'pm-team', name: 'Naruon PM 팀', colorClass: 'bg-red-500' },
  { id: 'product-team', name: '제품 개발팀', colorClass: 'bg-green-500' },
  { id: 'marketing', name: '마케팅팀', colorClass: 'bg-purple-500' },
  { id: 'company', name: '회사 공용', colorClass: 'bg-indigo-500' },
  { id: 'holiday', name: '공휴일', colorClass: 'bg-slate-400' },
];

export const calendarMonthEvents: CalendarMonthEvent[] = [
  {
    id: 'product-review',
    calendarId: 'product-team',
    dayIndex: 15,
    time: '10:00',
    title: '제품 리뷰',
    source: '제품 개발팀',
    description: '제품 개발팀 일정 원본의 리뷰 일정입니다.',
    monthClassName: 'bg-green-100 text-green-700',
    dotClassName: 'bg-green-500',
    badgeClassName: 'bg-green-100 text-green-700',
    badgeLabel: '팀 일정',
    duration: '1시간',
    location: '회의실 B (3층)',
  },
  {
    id: 'launch-meeting',
    calendarId: 'pm-team',
    dayIndex: 22,
    time: '09:30',
    title: '출시 회의',
    source: 'Naruon PM 팀',
    description: 'Naruon 2.0 출시 준비 및 일정 공유',
    monthClassName: 'bg-orange-100 text-orange-700',
    dotClassName: 'bg-orange-500',
    badgeClassName: 'bg-orange-100 text-orange-700',
    badgeLabel: '중요',
    duration: '1시간 30분',
    location: '회의실 A (4층)',
  },
];

export const calendarWeekEvents: CalendarWeekEvent[] = [
  { id: 'week-product-review', calendarId: 'product-team', day: '월', title: '제품 리뷰', source: '제품 개발팀' },
  { id: 'week-partner-meeting', calendarId: 'personal', day: '화', title: '파트너 미팅 후보', source: '김나루 (나)' },
  { id: 'week-resource-review', calendarId: 'company', day: '수', title: '리소스 배정 검토', source: '회사 공용' },
  { id: 'week-launch-meeting', calendarId: 'pm-team', day: '목', title: '출시 회의', source: 'Naruon PM 팀' },
  { id: 'week-marketing-kickoff', calendarId: 'marketing', day: '금', title: '마케팅 캠페인 오프', source: '마케팅팀' },
];

export const calendarCandidateEvents: CalendarCandidateEvent[] = [
  { id: 'candidate-partner', calendarId: 'personal', title: '파트너 미팅 일정 확정', source: '김나루 (나)', mode: '새 일정 반영 의도' },
  { id: 'candidate-launch', calendarId: 'pm-team', title: '출시 회의 시간 변경', source: 'Naruon PM 팀', mode: '충돌 검사 후 변경 의도' },
  { id: 'candidate-company', calendarId: 'company', title: '개인 메일에서 발견된 회사 일정', source: '회사 공용', mode: '원본 재지정 검토' },
];

export const calendarConflictPairs: CalendarConflictPair[] = [
  {
    pair_id: 'cancelled-allows',
    pair_label: '확정 제안 vs 취소된 기존 일정',
    proposed_ics: PROPOSED_CONFIRMED_1000Z_ICS,
    existing_ics: EXISTING_CANCELLED_1000Z_ICS,
  },
  {
    pair_id: 'tentative-review',
    pair_label: '확정 제안 vs 잠정 기존 일정',
    proposed_ics: PROPOSED_CONFIRMED_1000Z_ICS,
    existing_ics: EXISTING_TENTATIVE_1030Z_ICS,
  },
  {
    pair_id: 'confirmed-blocks',
    pair_label: '잠정 제안 vs 확정 기존 일정',
    proposed_ics: PROPOSED_TENTATIVE_1000Z_ICS,
    existing_ics: EXISTING_CONFIRMED_1000Z_ICS,
  },
];
