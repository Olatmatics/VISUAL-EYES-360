# 08 — Open Items / Information Required

These are unknowns that must not be guessed. Each blocks a specific phase. Nothing here is invented in the current documents.

| # | Missing information | Why it is required | Blocks |
|---|---|---|---|
| 1 | Exact Wayne dispenser model, CPU board, communication board, interface type and official protocol document | To write real preset/status/price/totalizer commands; guessing commands is prohibited | Phase 4 driver, Phase 10 |
| 2 | Gilbarco and Tatsuno protocol docs and interface hardware | For later drivers | Phase 10 expansion |
| 3 | OPay merchant/developer documentation, sandbox credentials, callback format/signature, supported products | To implement payment initiation and verification without inventing endpoints | Phase 9 |
| 4 | OPay POS terminal model and merchant-account capabilities (remote initiation, terminal ID, callbacks, SDK) | A payment API does not inherently control a POS terminal; confirm the workflow exists | Phase 7/9 |
| 5 | Approved bank-transfer provider product and callback/virtual-account docs | To implement verified transfers | Phase 9 |
| 6 | Cellular modem model, supported frequency bands, Nigerian operator compatibility (MTN/Airtel/Glo/9mobile), APNs, AT command set, power/SIM requirements | To implement SIM init, registration, APN, signal monitoring and power budget | Phase 2/4 |
| 7 | ATG probe model, RS485/Modbus register map, baud/parity, calibration chart format | To poll level/water/temp/ullage correctly | Phase 3/5 |
| 8 | RFID card technology and secure authentication method (e.g., DESFire-class with keys) | UID-only auth is prohibited; need secure credential design | Phase 2/4 |
| 9 | Pulser output spec (voltage, pulse rate, scaling/calibration basis) | To design the input circuit and confirm ESP32 capture is sufficient | Phase 2/4, STM32 decision |
| 10 | Nigerian states/LGA authoritative dataset source | Station management requires structured geography | Phase 6/7 |
| 11 | Installation site hazardous-area classification, electrical supply, grounding, enclosure and regulatory requirements | Safety review and certified interface selection | Phase 2/12 |
| 12 | Chosen ESP32-S3 board/module and available peripherals | Final pin allocation and conflict check | Phase 2 |
| 13 | Deployment target (cloud provider/region), domain/TLS, secret manager, backup policy | Backend infrastructure and initial setup token delivery | Phase 6/12 |
| 14 | Notification provider choices (email/SMS/push) and credentials | Alert delivery integrations | Phase 6/7 |
| 15 | Brand assets/colours/typography for UI | Professional UI theming | Phase 7 |

## Previous-session discrepancy (resolved for planning)

The prior agent claimed a background PostgreSQL 17 install and project-structure creation. Verification this session found neither: target folder empty, no PostgreSQL package/service/`psql`. Phase 1 does not depend on PostgreSQL; install it at Phase 6 with the superuser password supplied securely by the owner.
