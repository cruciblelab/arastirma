plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "lab.crucible.talktolinux"
    compileSdk = 35

    defaultConfig {
        applicationId = "lab.crucible.talktolinux"
        minSdk = 29
        targetSdk = 35
        versionCode = 29
        versionName = "0.22.0"
    }

    // Üç sürüm, aynı uygulama kimliği (biri diğerinin üzerine kurulabilir):
    //  tam   : bildirim erişimi var (bildirimler + telefondaki medya). Play Protect, internetten
    //          yüklenen ve bu izni isteyen uygulamaları bazı ülkelerde engelliyor; USB (adb) ile kurulur.
    //          Aramayı cevaplarken arka planda ekran açma engelini görünmez bir noktayla aşar (OVERLAY_TRICK).
    //  play  : Google Play'e uygun ("hilesiz"): tam sürümün aynısı, yalnızca "diğer uygulamaların üzerinde
    //          göster" izni ve o hile yok. Bilgisayar USB'de bunu görünce "Tam sürüme yükselt" der.
    //  hafif : bildirim erişimi yok; dosya yöneticisinden doğrudan kurulabilir.
    flavorDimensions += "surum"
    productFlavors {
        create("tam") {
            dimension = "surum"
            buildConfigField("boolean", "NOTIFICATIONS", "true")
            buildConfigField("boolean", "OVERLAY_TRICK", "true")
        }
        create("play") {
            dimension = "surum"
            versionNameSuffix = "-play"
            buildConfigField("boolean", "NOTIFICATIONS", "true")
            buildConfigField("boolean", "OVERLAY_TRICK", "false")
        }
        create("hafif") {
            dimension = "surum"
            versionNameSuffix = "-hafif"
            buildConfigField("boolean", "NOTIFICATIONS", "false")
            buildConfigField("boolean", "OVERLAY_TRICK", "false")
        }
    }

    // İmza anahtarı: TALKTO_KEYSTORE (dosya yolu) ve TALKTO_KEYSTORE_PASSWORD tanımlıysa onunla
    // imzalanır (GitHub Actions bunları depo sırlarından alır). Aynı anahtarla imzalanan yeni sürüm,
    // eskisinin üzerine kaldırmadan kurulur. Tanımlı değilse bu bilgisayarın hata ayıklama anahtarı kullanılır.
    val keystore = System.getenv("TALKTO_KEYSTORE")?.let { file(it) }?.takeIf { it.exists() }
    signingConfigs {
        if (keystore != null) {
            create("talkto") {
                storeFile = keystore
                storePassword = System.getenv("TALKTO_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("TALKTO_KEY_ALIAS") ?: "talktolinux"
                keyPassword = System.getenv("TALKTO_KEYSTORE_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.getByName(if (keystore != null) "talkto" else "debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    // Eşleşme karekodunu okumak: kamera (CameraX) ve çözücü (ZXing); ikisi de telefonda, internetsiz çalışır.
    val camerax = "1.4.1"
    implementation("androidx.camera:camera-camera2:$camerax")
    implementation("androidx.camera:camera-lifecycle:$camerax")
    implementation("androidx.camera:camera-view:$camerax")
    implementation("com.google.zxing:core:3.5.3")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
