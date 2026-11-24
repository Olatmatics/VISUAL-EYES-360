export interface UserContext {
  id: string
  user_id: string
  full_name: string
  role: string
  is_super_admin: boolean
  permissions: string[]
  stations: string[]
  all_stations: boolean
  must_change_password: boolean
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: UserContext
}

export interface GeoState {
  id: string
  name: string
  code: string | null
  lga_count: number
}

export interface GeoLga {
  id: string
  name: string
  state_id: string
}

export interface FuelProduct {
  id: string
  code: string
  name: string
}

export interface PumpType {
  id: string
  code: string
  name: string
  description: string | null
  is_active: boolean
}

export interface Station {
  id: string
  code: string
  name: string
  company_name?: string | null
  address: string | null
  country?: string
  state_id?: string | null
  lga_id?: string | null
  state_name?: string | null
  lga_name?: string | null
  city: string | null
  gps_lat?: string | null
  gps_lng?: string | null
  manager_name?: string | null
  manager_phone?: string | null
  manager_email?: string | null
  supervisor_name?: string | null
  supervisor_phone?: string | null
  supervisor_email?: string | null
  contact_person?: string | null
  phone: string | null
  email?: string | null
  notes?: string | null
  status: string
  registered_at: string
  dispenser_count?: number
  tank_count?: number
}

export interface Manager {
  id: string
  user_id: string
  full_name: string
  role?: string
  role_name?: string
  phone: string | null
  email: string | null
  is_active: boolean
  all_stations: boolean
  station_ids: string[]
  scope_state_id?: string | null
  scope_lga_id?: string | null
  permissions: string[]
  last_login_at: string | null
  created_at: string
}

export interface RoleOption {
  code: string
  name: string
  level: number
  permission_count?: number
}

export interface GeoOverview {
  states: number
  lgas: number
  stations: number
  states_with_stations: number
  lgas_with_stations: number
}

export interface DashboardSummary {
  stations: number
  active_stations: number
  dispensers: number
  nozzles: number
  tanks: number
  users: number
  total_revenue_ngn?: number
  total_volume_l?: number
  discrepancy_count?: number
  active_alerts?: number
}

export interface PermissionModule {
  code: string
  name: string
  actions: string[]
}

export interface DispenserNozzle {
  id: string
  number: number
  name?: string | null
  price: number
  status: string
  tank_id: string | null
  tank_code?: string | null
  product_id?: string | null
  product_code: string
  fcc_device_id: string | null
  fcc_uid: string | null
  fcc_online: boolean
  pos_terminal_id: string | null
}

export interface DispenserItem {
  id: string
  station_id: string
  station_name: string
  code: string
  name?: string | null
  manufacturer: string
  custom_manufacturer?: string | null
  brand?: string
  model: string
  pump_type_id?: string | null
  pump_type_name?: string | null
  nozzle_config?: string
  nozzle_count?: number
  protocol: string
  interface: string
  serial: string
  status: string
  communication_status?: string
  installation_date?: string | null
  totalizer_l: number
  nozzles: DispenserNozzle[]
}

export interface NozzleItem {
  id: string
  dispenser_id: string
  dispenser_code: string
  station_id: string
  station_name: string
  number: number
  price: number
  status: string
  product_code: string
  tank_id: string | null
  fcc: {
    id: string
    uid: string
    connection: string
    signal_dbm: number
    online: boolean
    cal_factor: number
  } | null
  pos: {
    terminal_id: string
    provider: string
    active: boolean
  } | null
}

export interface FCCDeviceItem {
  id: string
  device_uid: string
  name?: string | null
  serial_number?: string | null
  nozzle_id: string
  nozzle_number: number
  station_id?: string | null
  station_name: string
  dispenser_id?: string | null
  dispenser_code: string
  pos_terminal_id?: string | null
  pos_terminal_code?: string | null
  protocol?: string | null
  ip_address?: string | null
  mac_address?: string | null
  sim_info?: string | null
  hardware_version?: string | null
  firmware_version: string
  connection_mode: string
  signal_strength_dbm: number
  calibration_factor: number
  is_online: boolean
  status?: string
  installation_date?: string | null
  last_heartbeat: string | null
  temperature_c?: number | null
  power_status?: string | null
  hardware_fault?: string | null
  communication_errors?: number
}

export interface TankSensorItem {
  id: string
  sensor_type: string
  label: string | null
  is_installed: boolean
  is_enabled: boolean
  status: string
  last_reading_at: string | null
  notes: string | null
}

export interface TankCalibrationItem {
  id?: string
  height_mm: number
  volume_l: number
  water_mm?: number
}

export interface TankItem {
  id: string
  station_id: string
  station_name: string
  code: string
  name?: string | null
  serial_number?: string | null
  product_code: string
  product_name: string
  capacity_l: number
  current_volume_l: number
  current_level_mm: number
  current_water_mm: number
  current_temperature_c: number
  ullage_l: number
  fill_percentage: number
  hatch_open: boolean
  status: string
  location_type?: string
  position?: string | null
  dimensions?: string | null
  probe_id?: string | null
  probe_comm_type?: string | null
  monitoring_device?: string | null
  has_temperature_sensor?: boolean
  has_temperature_switch?: boolean
  has_tamper_switch?: boolean
  has_lid_limit_switch?: boolean
  has_high_level_switch?: boolean
  has_low_level_switch?: boolean
  has_water_detection?: boolean
  sensors?: TankSensorItem[]
  calibration?: TankCalibrationItem[]
  calibration_count?: number
  volume_from_calibration_l?: number | null
  controller: {
    id: string
    device_uid: string
    connection_mode: string
    signal_strength_dbm: number
    modbus_address: number
    is_online: boolean
  } | null
}

export interface TankReconciliationItem {
  id: string
  station_name: string
  tank_code: string
  shift_date: string
  opening_stock_l: number
  deliveries_l: number
  sales_cpu_l: number
  sales_pulser_l: number
  expected_closing_stock_l: number
  actual_atg_closing_stock_l: number
  variance_l: number
  variance_percentage: number
  status: string
  investigation_notes: string | null
  recorded_at: string
}

export interface TransactionItem {
  id: string
  transaction_ref: string
  station_id: string
  station_name: string
  dispenser_code: string
  nozzle_number: number
  product_code: string
  unit_price: number
  requested_amount: number
  requested_volume: number
  dispenser_cpu_volume: number
  independent_pulser_volume: number
  raw_pulse_count: number
  volume_difference: number
  discrepancy_alert: boolean
  investigation_status: string
  investigation_notes: string | null
  total_amount_billed: number
  payment_channel: string
  payment_ref: string
  status: string
  started_at: string
  completed_at: string | null
}

export interface PulserReconSummary {
  total_transactions: number
  total_cpu_volume_l: number
  total_pulser_volume_l: number
  cumulative_difference_l: number
  discrepancy_incidents: number
  compliance_rate_percent: number
  investigation_threshold_l: number
}

export interface POSTerminalItem {
  id: string
  terminal_id: string
  serial_number: string
  provider: string
  station_id: string
  station_name: string
  nozzle_id: string | null
  nozzle_number: number | null
  dispenser_code: string | null
  is_active: boolean
}

export interface PaymentRecordItem {
  id: string
  reference: string
  amount: number
  currency: string
  provider: string
  payment_method: string
  status: string
  pos_terminal_id: string | null
  created_at: string
}

export interface CustomerItem {
  id: string
  full_name: string
  phone: string
  email: string | null
  category: string
  is_active: boolean
  wallet: {
    balance: number
    reserved: number
    available: number
  } | null
  cards: {
    id: string
    card_uid: string
    is_blocked: boolean
    daily_spend_limit: number
  }[]
}

export interface FleetItem {
  id: string
  name: string
  code: string
  organization: string
  spending_limit: number
  status: string
  vehicle_count: number
  vehicles: {
    id: string
    plate_number: string
    vehicle_type: string
    driver_name: string
    fuel_type: string
    spending_limit: number
    odometer_km: number
  }[]
}

export interface PriceItem {
  nozzle_id: string
  nozzle_number: number
  dispenser_code: string
  station_id: string
  station_name: string
  product_code: string
  price: number
  status: string
}

export interface PriceHistoryItem {
  id: string
  station_id: string
  product_code: string
  previous_price: number
  new_price: number
  changed_by: string
  status: string
  created_at: string
}

export interface AlertItem {
  id: string
  alert_ref?: string
  station_id: string | null
  station_name: string
  category?: string
  alert_type: string
  severity: string
  title: string
  description: string
  entity_type: string | null
  entity_id: string | null
  device_type?: string | null
  device_id?: string | null
  expected_value?: number | null
  actual_value?: number | null
  discrepancy?: number | null
  state_id?: string | null
  lga_id?: string | null
  status?: string
  assigned_to?: string | null
  escalated?: boolean
  acknowledged_by?: string | null
  acknowledged_at?: string | null
  resolution_notes?: string | null
  is_resolved: boolean
  resolved_by: string | null
  created_at: string
  resolved_at: string | null
  updated_at?: string | null
}

export interface AlertSummary {
  total: number
  unresolved: number
  critical: number
  high: number
  by_category: { category: string; count: number }[]
  by_severity: { severity: string; count: number }[]
  by_state: { state: string; count: number }[]
  avg_resolution_hours?: number
}

export interface ReportsSummary {
  financial: {
    total_revenue_ngn: number
    opay_pos_ngn: number
    rfid_wallet_ngn: number
    bank_transfer_ngn: number
  }
  volumetric: {
    total_dispensed_cpu_l: number
    total_verified_pulser_l: number
    measurement_difference_l: number
    pms_volume_l: number
    ago_volume_l: number
    dpk_volume_l: number
  }
  inventory: {
    total_storage_capacity_l: number
    current_physical_stock_l: number
    ullage_available_l: number
    stock_fill_percentage: number
  }
  compliance: {
    total_transactions: number
    discrepancy_incidents: number
    compliance_rate_percent: number
    active_unresolved_alerts: number
  }
}

export interface RevenuePoint {
  label: string
  revenue_ngn: number
  volume_l: number
  transactions: number
}

export interface AnalyticsOverview {
  scope: string
  stations: number
  active_stations: number
  dispensers: number
  nozzles: number
  tanks: number
  fcc_online: number
  fcc_total: number
  transactions: number
  revenue_ngn: number
  volume_l: number
  discrepancy_incidents: number
  open_alerts: number
  stock_l: number
  capacity_l: number
  revenue_today_ngn?: number
  revenue_7d_ngn?: number
  revenue_30d_ngn?: number
  trend?: RevenuePoint[]
  by_product?: { code: string; volume_l: number; revenue_ngn: number }[]
  by_payment?: { channel: string; revenue_ngn: number }[]
  by_state?: { state: string; stations: number; revenue_ngn: number; volume_l: number }[]
}

export interface IngestEventItem {
  id: string
  device_uid: string
  device_type: string
  station_id: string | null
  event_type: string
  processing_status: string
  device_timestamp: string | null
  received_at: string
  detail: string | null
}
