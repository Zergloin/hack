import { Card, Col, Row, Statistic, Typography } from 'antd'
import {
  TeamOutlined,
  HeartOutlined,
  FallOutlined,
  SwapOutlined,
  RiseOutlined,
} from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import {
  fetchDemographicsSummary,
  fetchDemographicsTimeseries,
  fetchPopulationSummary,
  fetchPopulationTimeseries,
} from '@/api/population'
import { useFilterStore } from '@/store/useFilterStore'
import { formatDelta, formatPopulation, formatRate } from '@/utils/formatters'

function DeltaHint({
  value,
  formatter,
  positiveIsGood = true,
}: {
  value: number | null | undefined
  formatter: (value: number | null | undefined) => string
  positiveIsGood?: boolean
}) {
  if (value == null) {
    return <Typography.Text type="secondary">Нет сравнения</Typography.Text>
  }

  const color =
    value === 0
      ? '#718096'
      : positiveIsGood
        ? value > 0 ? '#237804' : '#cf1322'
        : value > 0 ? '#cf1322' : '#237804'

  return (
    <Typography.Text style={{ color, fontSize: 12 }}>
      к прошлому году: {formatter(value)}
    </Typography.Text>
  )
}

export default function KPICards() {
  const { municipalityId, regionId, yearFrom, yearTo } = useFilterStore()
  const previousYear = yearTo > yearFrom ? yearTo - 1 : null

  const { data: popSummary } = useQuery({
    queryKey: ['populationSummary', yearTo, regionId],
    queryFn: () => fetchPopulationSummary({ year: yearTo, region_id: regionId ?? undefined }),
    enabled: !municipalityId,
  })

  const { data: previousPopSummary } = useQuery({
    queryKey: ['populationSummary', previousYear, regionId],
    queryFn: () => fetchPopulationSummary({ year: previousYear!, region_id: regionId ?? undefined }),
    enabled: !municipalityId && previousYear != null,
  })

  const { data: demoSummary } = useQuery({
    queryKey: ['demographicsSummary', yearTo, regionId],
    queryFn: () => fetchDemographicsSummary({ year: yearTo, region_id: regionId ?? undefined }),
    enabled: !municipalityId,
  })

  const { data: previousDemoSummary } = useQuery({
    queryKey: ['demographicsSummary', previousYear, regionId],
    queryFn: () => fetchDemographicsSummary({ year: previousYear!, region_id: regionId ?? undefined }),
    enabled: !municipalityId && previousYear != null,
  })

  const { data: municipalityPopulationSeries = [] } = useQuery({
    queryKey: ['kpiPopulationTimeseries', municipalityId, previousYear, yearTo],
    queryFn: () =>
      fetchPopulationTimeseries({
        municipality_id: municipalityId ? [municipalityId] : [],
        year_from: previousYear ?? yearTo,
        year_to: yearTo,
      }),
    enabled: !!municipalityId,
  })

  const { data: municipalityDemographicsSeries = [] } = useQuery({
    queryKey: ['kpiDemographicsTimeseries', municipalityId, previousYear, yearTo],
    queryFn: () =>
      fetchDemographicsTimeseries({
        municipality_id: municipalityId ? [municipalityId] : [],
        year_from: previousYear ?? yearTo,
        year_to: yearTo,
      }),
    enabled: !!municipalityId,
  })

  const populationSeries = municipalityPopulationSeries[0]?.data ?? []
  const demographicsSeries = municipalityDemographicsSeries[0]?.data ?? []

  const currentPopulationPoint = populationSeries.find((point) => point.year === yearTo)
  const previousPopulationPoint =
    previousYear == null ? undefined : populationSeries.find((point) => point.year === previousYear)

  const currentDemographicsPoint = demographicsSeries.find((point) => point.year === yearTo)
  const previousDemographicsPoint =
    previousYear == null ? undefined : demographicsSeries.find((point) => point.year === previousYear)

  const populationValue = municipalityId ? currentPopulationPoint?.population : popSummary?.total_population
  const populationDelta = municipalityId
    ? currentPopulationPoint?.population != null && previousPopulationPoint?.population != null
      ? currentPopulationPoint.population - previousPopulationPoint.population
      : null
    : popSummary?.total_population != null && previousPopSummary?.total_population != null
      ? popSummary.total_population - previousPopSummary.total_population
      : null

  const naturalGrowthValue = municipalityId ? currentDemographicsPoint?.natural_growth : demoSummary?.total_natural_growth
  const naturalGrowthDelta = municipalityId
    ? currentDemographicsPoint?.natural_growth != null && previousDemographicsPoint?.natural_growth != null
      ? currentDemographicsPoint.natural_growth - previousDemographicsPoint.natural_growth
      : null
    : demoSummary?.total_natural_growth != null && previousDemoSummary?.total_natural_growth != null
      ? demoSummary.total_natural_growth - previousDemoSummary.total_natural_growth
      : null

  const birthRateValue = municipalityId ? currentDemographicsPoint?.birth_rate : demoSummary?.avg_birth_rate
  const birthRateDelta = municipalityId
    ? currentDemographicsPoint?.birth_rate != null && previousDemographicsPoint?.birth_rate != null
      ? Number((currentDemographicsPoint.birth_rate - previousDemographicsPoint.birth_rate).toFixed(2))
      : null
    : demoSummary?.avg_birth_rate != null && previousDemoSummary?.avg_birth_rate != null
      ? Number((demoSummary.avg_birth_rate - previousDemoSummary.avg_birth_rate).toFixed(2))
      : null

  const deathRateValue = municipalityId ? currentDemographicsPoint?.death_rate : demoSummary?.avg_death_rate
  const deathRateDelta = municipalityId
    ? currentDemographicsPoint?.death_rate != null && previousDemographicsPoint?.death_rate != null
      ? Number((currentDemographicsPoint.death_rate - previousDemographicsPoint.death_rate).toFixed(2))
      : null
    : demoSummary?.avg_death_rate != null && previousDemoSummary?.avg_death_rate != null
      ? Number((demoSummary.avg_death_rate - previousDemoSummary.avg_death_rate).toFixed(2))
      : null

  const migrationValue = municipalityId ? currentDemographicsPoint?.net_migration : demoSummary?.total_net_migration
  const migrationDelta = municipalityId
    ? currentDemographicsPoint?.net_migration != null && previousDemographicsPoint?.net_migration != null
      ? currentDemographicsPoint.net_migration - previousDemographicsPoint.net_migration
      : null
    : demoSummary?.total_net_migration != null && previousDemoSummary?.total_net_migration != null
      ? demoSummary.total_net_migration - previousDemoSummary.total_net_migration
      : null

  const cards = [
    {
      title: 'Население',
      value: populationValue,
      formatter: formatPopulation,
      delta: populationDelta,
      deltaFormatter: (value: number | null | undefined) => formatDelta(value),
      positiveIsGood: true,
      icon: <TeamOutlined style={{ color: '#2b6cb0' }} />,
      color: '#ebf8ff',
    },
    {
      title: 'Ест. прирост',
      value: naturalGrowthValue,
      formatter: formatPopulation,
      delta: naturalGrowthDelta,
      deltaFormatter: (value: number | null | undefined) => formatDelta(value),
      positiveIsGood: true,
      icon: <RiseOutlined style={{ color: '#38a169' }} />,
      color: '#f0fff4',
    },
    {
      title: 'Рождаемость',
      value: birthRateValue,
      formatter: formatRate,
      delta: birthRateDelta,
      deltaFormatter: (value: number | null | undefined) => (value == null ? '—' : `${value > 0 ? '+' : ''}${value.toFixed(2)}‰`),
      positiveIsGood: true,
      icon: <HeartOutlined style={{ color: '#d69e2e' }} />,
      color: '#fffbe6',
    },
    {
      title: 'Смертность',
      value: deathRateValue,
      formatter: formatRate,
      delta: deathRateDelta,
      deltaFormatter: (value: number | null | undefined) => (value == null ? '—' : `${value > 0 ? '+' : ''}${value.toFixed(2)}‰`),
      positiveIsGood: false,
      icon: <FallOutlined style={{ color: '#e53e3e' }} />,
      color: '#fff1f0',
    },
    {
      title: 'Миграция',
      value: migrationValue,
      formatter: formatPopulation,
      delta: migrationDelta,
      deltaFormatter: (value: number | null | undefined) => formatDelta(value),
      positiveIsGood: true,
      icon: <SwapOutlined style={{ color: '#805ad5' }} />,
      color: '#f9f0ff',
    },
  ]

  return (
    <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
      {cards.map((card) => (
        <Col xs={24} sm={12} lg={12} xl={4} key={card.title} flex="1">
          <Card className="kpi-card" size="small" style={{ background: card.color, borderColor: 'transparent' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
              <div style={{ flex: 1 }}>
                <Statistic
                  title={card.title}
                  value={card.value != null ? card.formatter(card.value as number) : '—'}
                  valueStyle={{ fontSize: 22, fontWeight: 600 }}
                />
                <DeltaHint value={card.delta} formatter={card.deltaFormatter} positiveIsGood={card.positiveIsGood} />
              </div>
              <div style={{ fontSize: 24, opacity: 0.6 }}>{card.icon}</div>
            </div>
          </Card>
        </Col>
      ))}
    </Row>
  )
}
