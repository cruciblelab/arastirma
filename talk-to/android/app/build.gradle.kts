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
        versionCode = 7
        versionName = "0.4.0"
    }

    // İki sürüm, aynı uygulama kimliği (biri diğerinin üzerine kurulabilir):
    //  tam   : bildirim erişimi var (bildirimler + telefondaki medya). Play Protect, internetten
    //          yüklenen ve bu izni isteyen uygulamaları bazı ülkelerde engelliyor; USB (adb) ile kurulur.
    //  hafif : bildirim erişimi yok; dosya yöneticisinden doğrudan kurulabilir.
    flavorDimensions += "surum"
    productFlavors {
        create("tam") {
            dimension = "surum"
            buildConfigField("boolean", "NOTIFICATIONS", "true")
        }
        create("hafif") {
            dimension = "surum"
            versionNameSuffix = "-hafif"
            buildConfigField("boolean", "NOTIFICATIONS", "false")
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

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
