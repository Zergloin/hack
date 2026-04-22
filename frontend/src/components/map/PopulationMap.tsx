import { useEffect, useState, useCallback } from 'react'
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet'
import { Button, Spin, Drawer, Statistic, Row, Col, message } from 'antd'
import { BulbOutlined } from '@ant-design/icons'
import type { Layer, LeafletMouseEvent } from 'leaflet'
import { useQuery } from '@tanstack/react-query'
import { fetchMapGeoJSON, fetchMapDensity } from '@/api/population'
import { getAIInsight } from '@/api/chat'
import { getPopulationColor } from '@/utils/colors'
import { formatPopulation } from '@/utils/formatters'
import 'leaflet/dist/leaflet.css'

function MapController() {
  const map = useMap()
  useEffect(() => {
    map.setView([62, 95], 3)
  }, [map])
  return null
}

export default function PopulationMap() {
  const [selectedRegion, setSelectedRegion] = useState<any>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [insightLoading, setInsightLoading] = useState(false)
  const [insight, setInsight] = useState('')

  const { data: geojson, isLoading } = useQuery({
    queryKey: ['map-geojson'],
    queryFn: () => fetchMapGeoJSON({ level: 'region', year: 2022 }),
  })

  const { data: densityData = [] } = useQuery({
    queryKey: ['map-density'],
    queryFn: () => fetchMapDensity({ year: 2022 }),
  })

  const densityMap = new Map(densityData.map((d: any) => [d.code, d]))

  const onEachFeature = useCallback((feature: any, layer: Layer) => {
    const props = feature.properties || {}
    const name = props.db_name || props.name || props.NAME_1 || 'Неизвестно'
    const pop = props.population

    layer.bindTooltip(
      `<strong>${name}</strong><br/>Население: ${pop ? formatPopulation(pop) : '—'}`,
      { sticky: true }
    )

    layer.on({
      click: () => {
        setSelectedRegion({ ...props, name })
        setDrawerOpen(true)
        setInsight('')
      },
      mouseover: (e: LeafletMouseEvent) => {
        const target = e.target
        target.setStyle({ weight: 3, fillOpacity: 0.8 })
      },
      mouseout: (e: LeafletMouseEvent) => {
        const target = e.target
        target.setStyle({ weight: 1, fillOpacity: 0.6 })
      },
    })
  }, [])

  const getStyle = useCallback((feature: any) => {
    const props = feature?.properties || {}
    const pop = props.population || 0
    return {
      fillColor: getPopulationColor(pop),
      weight: 1,
      color: '#fff',
      fillOpacity: 0.6,
    }
  }, [])

  const handleAIInsight = async () => {
    if (!selectedRegion?.db_id) return
    setInsightLoading(true)
    try {
      const result = await getAIInsight({ region_id: selectedRegion.db_id })
      setInsight(result.insight)
    } catch {
      message.error('Не удалось получить AI-инсайт')
    } finally {
      setInsightLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spin size="large" tip="Загрузка карты..." />
      </div>
    )
  }

  return (
    <div style={{ height: '100%', position: 'relative' }}>
      <MapContainer
        center={[62, 95]}
        zoom={3}
        style={{ height: '100%', width: '100%', borderRadius: 8 }}
        zoomControl={true}
      >
        <MapController />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {geojson?.features?.length > 0 && (
          <GeoJSON
            key={JSON.stringify(geojson).slice(0, 100)}
            data={geojson}
            onEachFeature={onEachFeature}
            style={getStyle}
          />
        )}
      </MapContainer>

      {/* Legend */}
      <div
        style={{
          position: 'absolute',
          bottom: 30,
          left: 10,
          background: 'white',
          padding: '12px 16px',
          borderRadius: 8,
          boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          zIndex: 1000,
          fontSize: 12,
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: 8 }}>Население</div>
        {[
          { color: '#1a365d', label: '> 1 млн' },
          { color: '#2b6cb0', label: '500К — 1М' },
          { color: '#3182ce', label: '200К — 500К' },
          { color: '#4299e1', label: '100К — 200К' },
          { color: '#63b3ed', label: '50К — 100К' },
          { color: '#90cdf4', label: '20К — 50К' },
          { color: '#bee3f8', label: '< 20К' },
        ].map((item) => (
          <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
            <div style={{ width: 16, height: 12, background: item.color, borderRadius: 2 }} />
            <span>{item.label}</span>
          </div>
        ))}
      </div>

      {/* AI Insight Button */}
      <Button
        type="primary"
        icon={<BulbOutlined />}
        style={{
          position: 'absolute',
          top: 10,
          right: 10,
          zIndex: 1000,
          borderRadius: 20,
        }}
        onClick={handleAIInsight}
        loading={insightLoading}
        disabled={!selectedRegion}
      >
        AI Инсайт
      </Button>

      {/* Detail Drawer */}
      <Drawer
        title={selectedRegion?.name || 'Регион'}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={380}
      >
        {selectedRegion && (
          <>
            <Row gutter={[16, 16]}>
              <Col span={24}>
                <Statistic
                  title="Население"
                  value={selectedRegion.population ? formatPopulation(selectedRegion.population) : '—'}
                />
              </Col>
            </Row>

            {insight && (
              <div
                style={{
                  marginTop: 24,
                  padding: 16,
                  background: '#f0f7ff',
                  borderRadius: 8,
                  borderLeft: '4px solid #2b6cb0',
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: 8, color: '#2b6cb0' }}>
                  AI Инсайт
                </div>
                <div style={{ lineHeight: 1.6 }}>{insight}</div>
              </div>
            )}
          </>
        )}
      </Drawer>
    </div>
  )
}
