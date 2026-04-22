import { Row, Col, Card, Statistic } from 'antd'
import {
  TeamOutlined,
  RiseOutlined,
  HeartOutlined,
  FallOutlined,
  SwapOutlined,
} from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { fetchPopulationSummary, fetchDemographicsSummary } from '@/api/population'
import { useFilterStore } from '@/store/useFilterStore'
import { formatPopulation, formatRate } from '@/utils/formatters'

export default function KPICards() {
  const { regionId, yearTo } = useFilterStore()

  const { data: popSummary } = useQuery({
    queryKey: ['populationSummary', yearTo, regionId],
    queryFn: () => fetchPopulationSummary({ year: yearTo, region_id: regionId ?? undefined }),
  })

  const { data: demoSummary } = useQuery({
    queryKey: ['demographicsSummary', yearTo, regionId],
    queryFn: () => fetchDemographicsSummary({ year: yearTo, region_id: regionId ?? undefined }),
  })

  const cards = [
    {
      title: 'Население',
      value: popSummary?.total_population,
      formatter: formatPopulation,
      icon: <TeamOutlined style={{ color: '#2b6cb0' }} />,
      color: '#ebf8ff',
    },
    {
      title: 'Муниципалитетов',
      value: popSummary?.total_municipalities,
      formatter: (v: number) => v?.toLocaleString('ru-RU') ?? '—',
      icon: <RiseOutlined style={{ color: '#38a169' }} />,
      color: '#f0fff4',
    },
    {
      title: '��ождаемость',
      value: demoSummary?.avg_birth_rate,
      formatter: formatRate,
      icon: <HeartOutlined style={{ color: '#d69e2e' }} />,
      color: '#fffff0',
    },
    {
      title: 'Смертность',
      value: demoSummary?.avg_death_rate,
      formatter: formatRate,
      icon: <FallOutlined style={{ color: '#e53e3e' }} />,
      color: '#fff5f5',
    },
    {
      title: 'Миграция (ср.)',
      value: demoSummary?.avg_net_migration_rate,
      formatter: formatRate,
      icon: <SwapOutlined style={{ color: '#805ad5' }} />,
      color: '#faf5ff',
    },
  ]

  return (
    <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
      {cards.map((card) => (
        <Col xs={24} sm={12} lg={4} xl={4} key={card.title} flex="1">
          <Card
            className="kpi-card"
            size="small"
            style={{ background: card.color, borderColor: 'transparent' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <Statistic
                title={card.title}
                value={card.value != null ? card.formatter(card.value as any) : '—'}
                valueStyle={{ fontSize: 22, fontWeight: 600 }}
              />
              <div style={{ fontSize: 24, opacity: 0.6 }}>{card.icon}</div>
            </div>
          </Card>
        </Col>
      ))}
    </Row>
  )
}
