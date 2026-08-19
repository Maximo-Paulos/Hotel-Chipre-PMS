# Capacitor release guide

App id: `com.hotelchipre.pms` (set in `capacitor.config.ts`). App name: `Hotel Chipre PMS`.

## Local build/sync workflow

```sh
npm run build          # Vite build → dist/
npx cap sync            # copies dist/ into ios/ and android/, updates native plugins
npx cap open ios        # opens ios/App/App.xcworkspace in Xcode
npx cap open android    # opens android/ in Android Studio
```

Run `npx cap sync <platform>` (not `--no-sync`) whenever `dist/` changes — a stale sync means
the native shell runs old JS with none of your latest fixes. `npx cap run ios --target <udid>`
(get the UDID from `xcrun simctl list devices | grep Booted`) builds, installs, and launches on
an already-booted Simulator non-interactively, no picker prompt.

## API base URL for a real device / store build

`src/api/client.ts` defaults to `http://127.0.0.1:8040/api` (the Simulator can reach the host
Mac directly, so this works for `npx cap run ios` against a local dev backend). A physical
device or any build submitted to the App Store / Play Store **cannot** reach `127.0.0.1` — it
must be built with the deployed backend URL:

```sh
VITE_API_URL=https://<render-service>.onrender.com/api npm run build
npx cap sync
```

`<render-service>` is whatever `APP_BASE_URL` is set to in the real production backend env (see
`.env.example`'s PRODUCTION section — the repo only ships a placeholder,
`APP_BASE_URL=https://<tu-servicio>.onrender.com`; the real value lives in the deployed Render
service config, not in this repo).

## Icon / splash asset status

`assets/icon.png` and `assets/splash.png` are both **512x512**. Apple requires a **1024x1024**
source icon for the App Store listing (`@capacitor/assets generate` upsizes what it's given, so
the generated app-icon set is present but soft/blurry at the largest App Store sizes). Before a
real submission, replace both files with true 1024x1024 sources and rerun:

```sh
npx @capacitor/assets generate
npx cap sync
```

## Manual path to publish (cannot be automated by an agent)

**iOS**
1. Enroll in the Apple Developer Program ($99/yr) — user's own Apple ID + payment, done outside this repo.
2. Create the app record in App Store Connect, registering bundle id `com.hotelchipre.pms`.
3. In Xcode (`npx cap open ios`), set the signing team and provisioning profile for the `App` target.
4. Prepare required App Store screenshots per device size (6.9", 6.5", 5.5" iPhone; iPad sizes if supporting iPad).
5. Provide a hosted privacy policy URL (App Store Connect requires one).
6. Archive (`Product > Archive`) and upload via Xcode Organizer, or `npx cap open ios` → Archive → Distribute App.

**Android**
1. Enroll in Google Play Console ($25 one-time) — user's own account + payment.
2. Create the app listing, complete the Play Data Safety form (what data the app collects/shares — check `app/config.py` and this app's actual API usage before answering it).
3. Generate/configure a signing key in Android Studio (`npx cap open android` → Build > Generate Signed Bundle).
4. Prepare required Play Store screenshots and feature graphic.
5. Build an Android App Bundle (`.aab`) and upload it via Play Console (or Android Studio's "Upload" flow).

None of the steps above can be done by an agent — they require the user's own developer account
credentials, payment, and manual App Store Connect / Play Console interaction.
