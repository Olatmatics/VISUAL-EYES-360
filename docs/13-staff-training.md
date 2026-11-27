# 13 — Staff training: from customer arrival to the last step

This is a **bench/prototype training guide**. It is not safe for a live forecourt,
is not intrinsically safe, and does not implement a real dispenser protocol.
Development boards are not certified for hazardous areas. Mock OPay sandbox
references are **not** proof of payment.

Teach this guide in the order shown. A new staff member should not touch wiring,
upload code, reset data, or use live credentials. Their job is to observe the
screens, type the listed Serial commands, handle the customer, and report any
difference immediately.

---

## 1. The three rules a staff member must repeat

1. **No verified payment, no dispensing.** A screenshot, receipt, voice note or
   "I have paid" is not approval. The software must show `PAYMENT_SUCCESS` and the
   board must `ACK` it.
2. **Approval only arms the transaction.** It does **not** energise the nozzle
   switch, start the motor, or send pulses. The physical nozzle switch/relay
   contact is the start event.
3. **The software is the truth.** The card, the POS terminal and the board are
   only messengers. Identity, balance, authorization and the final litres live in
   the backend and are visible in **Fuel Transactions**, **Pulser Verification**
   and **Hardware JSON Monitor**.

---

## 2. The tools the staff member will use

### Web pages

| Page | Why the staff member opens it |
|---|---|
| **Operations Dashboard** | First screen after login. Top ticker shows which devices are online. A device counts as online only if its heartbeat is inside **240 seconds**. |
| **Forecourt & Dispense** | Select a nozzle and start a preset simulation amount. This calls the same backend transaction-initiate endpoint as Board 1 `INIT`. |
| **Fuel Transactions** | Confirms the final record: reference, amount, litres, status and station. |
| **RFID Special Wallets** | Shows registered cards, nationwide balance and funding history. |
| **OPay POS & Cashless** | Shows POS terminals. A terminal **must be assigned to the nozzle** before `INIT` will work. |
| **Pulse MATH (Serial + Web)** | Shows `pulses_per_litre` (PPL). Both the FCC and independent pulser use this same value. |
| **Hardware JSON Monitor** | Shows every IN/OUT JSON message. Use it when you need to prove what the board sent or received. |
| **Pulser Verification (0.49L)** | Compares Board 1 litres with the independent Board 3 pulser. |
| **Device ID Directory** | Copy buttons for station, pump, nozzle, FCC and POS short codes. |
| **Start Here · Set Up** | One-time setup summary. Admin/setup staff only. |
| **Generate Hardware IDs** | Superior Administrator only. Creates short copyable IDs and ESP32 code blocks. |
| **Audit Log Trail / User Management** | Admin only; used to check who changed what. |

### Boards and what they mean

| Board | Staff sees | Main commands |
|---|---|---|
| **1 — FCC controller** | Starts payment, waits for approval, counts litres, stops at target, posts COMPLETE. GPIO2 steady ON = Wi-Fi connected. GPIO22 external LED fast-blinks = backend traffic. | `HELP`, `NETWORK`, `PING`, `STATUS`, `NOZZLE A/B`, `INIT 5000`, `POLL`, `ACK <id>`, `COMPLETE <L>`, `RESET`, `HEARTBEAT`, `JSON ON`, `CONFIG` |
| **2 — Tank monitor** | Reads tank level/temperature and lid switch. | `READ`, `SEND`, `STATUS` |
| **3 — Independent pulser** | Counts pulses from Board 4 and converts to litres. Separate from Board 1. | `COUNT`, `MATH 1000`, `MATH RATE 10`, `SEND`, `STATUS` |
| **4 — Pulse simulator** | Turns the motor on and generates pulses when Board 1 triggers it. GPIO2 blinks **once per pulse**. No Wi-Fi. | `HELP`, `STATUS`, `RATE 1000`, `BURST 100`, `START`, `STOP` |
| **5 — RFID reader** | Reads card UID, registers/funds/pays from the wallet. | `REGISTER`, `CARD`, `SCAN`, `NAME <name>`, `SAVE`, `FUND 5000`, `PAY 5000`, `CANCEL`, `STATUS` |

All boards use **Serial Monitor at 115200 baud**. The backend URL in every sketch
must be `http://172.25.0.37:8000` — never `localhost`.

---

## 3. Opening checklist — before the first customer

Do this every day before you attend a customer.

1. **Start the software.** Confirm the web app opens at
   `http://127.0.0.1:5173` and the backend answers at
   `http://172.25.0.37:8000/health` with `{"status":"ok"}`.
2. **Log in with your own account.** Use the Manager login for daily work. Do not
   use the Superior Administrator login unless you are doing setup. Admin login
   on this bench is `SUPERADMIN001 / Admin@1234`; protect it.
3. **Check the ticker.** On **Operations Dashboard**, the devices you need must be
   online. If a device is missing, wait for the next heartbeat (Board 1 sends one
   every 30 seconds) or type `HEARTBEAT` on Board 1.
4. **Check the LEDs.** On Boards 1, 2, 3 and 5, GPIO2 must be **steady ON** when
   connected. Slow blink means still joining Wi-Fi. GPIO22 fast-blink means
   backend activity. Board 4's GPIO2 blinks per pulse; that is normal.
5. **Check Board 1** in Serial Monitor:
   ```text
   NETWORK
   PING
   STATUS
   JSON ON
   ```
   You want `STATUS=CONNECTED`, an IP address, `PING -> 200`, and `WIFI=OK`.
6. **Check Board 4** in Serial Monitor:
   ```text
   HELP
   STATUS
   ```
   Confirm it reports GPIO27 motor output and that the motor/pulses are **off**
   until a nozzle trigger arrives.
7. **Check Board 3** in Serial Monitor:
   ```text
   STATUS
   COUNT
   SEND
   ```
   Confirm the PPL matches **Pulse MATH** on the web.
8. **Check the assignments in the web.** Confirm station, dispenser, nozzle, FCC
   UID and **POS terminal assigned to that nozzle**. The most common failure is
   a POS terminal registered but not assigned to a nozzle.
9. **Have the short codes ready.** Use **Device ID Directory** or **Generate
   Hardware IDs** to copy `ST-...`, `PMP-...`, `NZ-...`, `FCC-...`, `POS-...`.
   Staff never need to copy long UUIDs.
10. **Prepare cards before the queue builds.** Register and fund wallet cards in
    advance; do not fund a card while a customer is waiting unless the payment is
    already verified.

---

## 4. Customer journey A — POS / OPay payment

Use this when the customer pays at the POS terminal.

### Step 1 — Choose the nozzle and amount

1. Ask the customer which nozzle/product they want.
2. In the web, open **Forecourt & Dispense**, select the nozzle, enter the preset
   amount in naira, for example `5000`, and start the transaction.
   **Or** on Board 1 Serial Monitor type:
   ```text
   NOZZLE A
   INIT 5000
   ```
   For a litre preset you may type `INIT 5L` instead.
3. Board 1 prints the JSON request. It calls
   `POST /api/v1/fcc/transaction/initiate`. If the reply says
   `No POS terminal assigned to this nozzle`, **stop** and ask the administrator
   to assign the POS terminal in **OPay POS & Cashless**. Do not improvise.

### Step 2 — Customer pays at the POS

1. The customer pays on the POS terminal. On the bench, **mock OPay** posts the
   webhook about 3.5 seconds after payment creation.
2. The backend verifies the webhook signature and queues `PAYMENT_SUCCESS` in
   `device_commands`.
3. Do **not** rely on the POS screen alone. The board must collect the command.

### Step 3 — Collect and acknowledge approval

On Board 1 Serial Monitor type:

```text
POLL
```

Look for a queued command with reference like `PAYMENT-...` and status
`PAYMENT_SUCCESS`. Then type:

```text
ACK <that command reference>
```

Now type:

```text
STATUS
```

You should see state `AUTHORIZED` and the authorised litres.

**Still nothing should move.** The valve relay is not energised, the motor is off,
and Board 4 is not pulsing. This is intentional.

### Step 4 — Let the customer operate the nozzle switch

1. The customer/operator closes the external nozzle relay contact.
2. On the bench this means Board 01 `GPIO13` (nozzle A) or `GPIO12` (nozzle B) is
   connected to GND through the relay contact.
3. Board 01 raises `GPIO32` HIGH. That line goes to Board 04 `GPIO25`.
4. Board 04 automatically turns the motor ON through `GPIO27` and starts pulses.
   Its GPIO2 LED blinks once per pulse.
5. Board 01 and Board 03 both count the pulses independently.

### Step 5 — Watch the litres

While dispensing:

```text
Board 1: STATUS     shows FCC litres and authorised litres
Board 3: COUNT      shows raw pulses and independent litres
Web: Hardware JSON Monitor shows the IN/OUT messages
```

When Board 01 reaches the authorised litres it stops `GPIO32`. Board 04 turns the
motor OFF and stops pulses. Board 01 POSTs `COMPLETE` with litres, pulses and the
comparison against the independent pulser.

If you are doing a fully manual bench test, type:

```text
COMPLETE <measured litres>
```

### Step 6 — Close the customer transaction

1. Open **Fuel Transactions**. Confirm the row shows:
   - correct customer/POS reference,
   - correct nozzle and product,
   - amount and litres,
   - status `COMPLETED`,
   - correct station.
2. Open **Pulser Verification (0.49L)** or the transaction comparison. Confirm the
   FCC litres and independent pulser litres are close. If they differ, do not
   argue with the customer — report it and keep the record.
3. On Board 1 type:
   ```text
   RESET
   ```
   Confirm the state returns to `IDLE` and the trigger is OFF.
4. Return the nozzle switch to its open/rest position.
5. Give the customer the receipt/reference from the web record, thank them, and
   clear the nozzle for the next customer.

---

## 5. Customer journey B — RFID special wallet

A card is **nationwide**. `home_station_id` only records where it was first
registered; it does not restrict where the card can be used. The card contains
only a UID — the backend owns balance and authorization.

### Phase 1 — Register a new customer card (manager)

Do this before the customer pays, or at the desk.

1. On Board 5 Serial Monitor type:
   ```text
   REGISTER
   ```
2. When it prints `Place the NEW customer card (30s)`, place the card on the
   MFRC522 reader.
3. Serial prints the UID, for example `UID READ: A1B2C3D4`.
4. Type the owner name:
   ```text
   NAME Alu Ada
   ```
5. Type:
   ```text
   SAVE
   ```
6. Confirm the reply shows `NATIONWIDE: YES`, owner, home station and balance.
7. Check **RFID Special Wallets** in the web — the card must be listed there.

### Phase 2 — Fund the wallet

Only after a verified cash/bank/POS payment, on Board 5:

```text
SCAN
FUND 5000
```

Confirm the new balance. Never fund because someone says "I will pay later".

### Phase 3 — Customer pays at the pump with the card

1. Customer places the card on Board 5.
2. Staff types:
   ```text
   SCAN
   ```
   Confirm the UID and available balance.
3. Type:
   ```text
   PAY 5000
   ```
   Board 5 debits the wallet and queues `PAYMENT_SUCCESS` for the nozzle set in
   `SET NOZZLE`. This uses the **same** backend approval path as OPay and creates
   a verified `PaymentRecord`.
4. Go to Board 1 and continue from **Step 3 — Collect and acknowledge approval**
   above: `POLL`, `ACK <ref>`, `STATUS`, then the nozzle switch, pulses,
   litres and `COMPLETE`.
5. Finish with the same **Step 6 — Close the customer transaction** checks.

---

## 6. Fault script — what to say and do

| What you see | Meaning | Staff action |
|---|---|---|
| `INIT` replies `No POS terminal assigned to this nozzle` | POS terminal exists but is not linked to the nozzle. | Stop. Ask administrator to assign it under **OPay POS & Cashless**. |
| `PING` does not show `-> 200` | Board cannot reach backend. | Check the PC backend, Wi-Fi and that the sketch uses `172.25.0.37`, not `localhost`. Do not dispense. |
| GPIO2 slowly blinking on Boards 1/2/3/5 | Still joining Wi-Fi. | Check `cypher` is **2.4 GHz**, password `12345678`, board near router. Type `WIFI` to retry. |
| Board stops before `[WIFI] begin called` | Wi-Fi driver/flash/power problem. | Ask technician to re-upload the latest sketch; if still stuck, use `00_wifi_test` and erase flash. |
| `PAYMENT_SUCCESS` but no pulses | Approval only armed; nozzle switch never closed. | Ask customer/operator to close the external relay contact. Never energise the nozzle from software. |
| Motor not spinning but pulses command present | GPIO27 is only a logic signal. | Technician checks motor driver input, separate motor supply and common GND. |
| Board 3 litres differ from Board 1 | PPL mismatch or wiring/counting fault. | Check **Pulse MATH** and `CAL FETCH` on both boards. Report; do not guess a new PPL. |
| Ticker shows device offline | No heartbeat inside 240 seconds. | On Board 1 type `HEARTBEAT`; check Wi-Fi LED and `PING`. |
| Card not recognised | UID not registered or card not placed correctly. | Re-place card; if still unknown, manager registers it with `REGISTER` → `SAVE`. |
| Wallet says insufficient balance | Card balance too low. | Fund only after a verified payment, using `FUND`. |
| No JSON visible on screen | Serial echo disabled or web monitor not open. | Board: `JSON ON`. Web: open **Hardware JSON Monitor**. |
| `[RELAY] outputs OFF ...` at boot | Normal safety message. | Ignore; it means firmware is not energising the nozzle switch. |

---

## 7. Closing checklist — every customer

- [ ] Transaction status is `COMPLETED` in **Fuel Transactions**.
- [ ] Reference, amount, litres, nozzle and station are correct.
- [ ] Independent pulser comparison checked.
- [ ] Board 1 `RESET` done; state back to `IDLE`.
- [ ] Board 4 motor and pulses stopped.
- [ ] Nozzle switch returned to rest.
- [ ] Card removed and returned to customer.
- [ ] Receipt/reference given to customer.
- [ ] Any discrepancy reported immediately and left in the audit trail.

---

## 8. What staff must never do

- Never use this bench setup on a real forecourt or with real fuel.
- Never claim a mock OPay reference is payment proof.
- Never share the Superior Administrator password.
- Never paste API keys, OPay private keys or Telegram bot tokens into a sketch.
  OPay secrets belong in `.env` only.
- Never put `localhost` in an ESP32 sketch.
- Never power a motor directly from an ESP32 GPIO.
- Never reset stations, users, roles, states, LGAs or products unless an authorised
  administrator explicitly asks.
- Never edit or delete a completed transaction to "make it look right". Report the
  problem instead.

---

## 9. Trainer's one-minute rehearsal script

> Trainer: "A customer arrives and says they have paid. What do you check first?"
>
> Trainee: "I check the web ticker and Board 1 `STATUS`/`PING`. I do not trust the
> customer's screenshot."
>
> Trainer: "The POS screen shows paid. What next?"
>
> Trainee: "On Board 1 I type `POLL`, then `ACK` the `PAYMENT_SUCCESS` reference.
> The board becomes AUTHORIZED but nothing moves yet."
>
> Trainer: "Why has nothing moved?"
>
> Trainee: "Because approval only arms. The nozzle switch relay contact must be
> closed by the operator/customer. Then Board 04 starts the motor and pulses."
>
> Trainer: "How do you finish?"
>
> Trainee: "Board 1 stops at the authorised litres, Board 04 stops, I check the
> litres on Board 1 and Board 3, confirm **Fuel Transactions** and **Pulser
> Verification**, then type `RESET` and give the customer the reference."
>
> Trainer: "What do you do if the two litres disagree?"
>
> Trainee: "I do not argue or edit the record. I report it and we check PPL and
> the audit trail."

---

## 10. Sign-off checklist

The trainee is ready when they can do all of these without help:

- [ ] Log in with their own role and find the ticker.
- [ ] Say what a steady GPIO2 LED and a fast GPIO22 blink mean.
- [ ] Register and fund a wallet card.
- [ ] Start `INIT 5000` from the web or Board 1.
- [ ] `POLL` and `ACK` a `PAYMENT_SUCCESS`.
- [ ] Explain why approval does not energise the nozzle switch.
- [ ] Operate the bench nozzle switch safely and watch the pulses.
- [ ] Read litres from Board 1 and Board 3.
- [ ] Confirm the final record in **Fuel Transactions**.
- [ ] Check **Pulser Verification**.
- [ ] `RESET` Board 1 and restore the nozzle to rest.
- [ ] Report a fault without changing records.
