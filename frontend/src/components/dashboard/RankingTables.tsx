import { Row, Col, Card, Table, Tag } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { fetchPopulationRankings } from '@/api/population'
import { useFilterStore } from '@/store/useFilterStore'
import { formatNumber, formatPercent } from '@/utils/formatters'

const columns = [
  {
    title: 'Муниципалитет',
    dataIndex: 'municipality_name',
    key: 'name',
    ellipsis: true,
    width: '35%',
  },
  {
    title: 'Регион',
    dataIndex: 'region_name',
    key: 'region',
    ellipsis: true,
    width: '25%',
    render: (v: string) => <span style={{ color: '#718096', fontSize: 12 }}>{v}</span>,
  },
  {
    title: 'Изменение',
    dataIndex: 'change_percent',
    key: 'change',
    width: '20%',
    render: (v: number | null) => {
      if (v == null) return '—'
      return (
        <Tag color={v > 0 ? 'green' : 'red'}>
          {formatPercent(v)}
        </Tag>
      )
    },
  },
  {
    title: 'Население',
    dataIndex: 'population_end',
    key: 'pop',
    width: '20%',
    render: (v: number | null) => formatNumber(v),
  },
]

export default function RankingTables() {
  const { regionId, yearFrom, yearTo, setRegionId, setMunicipalityId } = useFilterStore()

  const { data: growth = [], isLoading: loadingGrowth } = useQuery({
    queryKey: ['rankings-growth', regionId, yearFrom, yearTo],
    queryFn: () =>
      fetchPopulationRankings({
        year_from: yearFrom,
        year_to: yearTo,
        order: 'desc',
        limit: 10,
        region_id: regionId ?? undefined,
      }),
  })

  const { data: decline = [], isLoading: loadingDecline } = useQuery({
    queryKey: ['rankings-decline', regionId, yearFrom, yearTo],
    queryFn: () =>
      fetchPopulationRankings({
        year_from: yearFrom,
        year_to: yearTo,
        order: 'asc',
        limit: 10,
        region_id: regionId ?? undefined,
      }),
  })

  return (
    <Row gutter={16}>
      <Col xs={24} lg={12}>
        <Card
          title="Лидеры роста населения"
          size="small"
          style={{ marginBottom: 16 }}
        >
          <Table
            dataSource={growth}
            columns={columns}
            loading={loadingGrowth}
            pagination={false}
            size="small"
            rowKey="municipality_id"
            scroll={{ x: 500 }}
            onRow={(record) => ({
              onClick: () => {
                setRegionId(record.region_id)
                setMunicipalityId(record.municipality_id)
              },
              style: { cursor: 'pointer' },
            })}
          />
        </Card>
      </Col>
      <Col xs={24} lg={12}>
        <Card
          title="Лидеры убыли населения"
          size="small"
          style={{ marginBottom: 16 }}
        >
          <Table
            dataSource={decline}
            columns={columns}
            loading={loadingDecline}
            pagination={false}
            size="small"
            rowKey="municipality_id"
            scroll={{ x: 500 }}
            onRow={(record) => ({
              onClick: () => {
                setRegionId(record.region_id)
                setMunicipalityId(record.municipality_id)
              },
              style: { cursor: 'pointer' },
            })}
          />
        </Card>
      </Col>
    </Row>
  )
}
