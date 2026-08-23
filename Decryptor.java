import android.content.Context;
import android.os.Looper;
import android.os.Build;
import android.content.pm.PackageInfo;
import android.content.pm.Signature;
import java.lang.reflect.Method;
import java.lang.reflect.Field;
import java.lang.reflect.Proxy;
import java.lang.reflect.InvocationHandler;

public class Decryptor implements InvocationHandler {
    // Original developer's signing certificate DER bytes (Avantika Doshi)
    // Extracted from SportzX_v2.5.apk META-INF/CERT.RSA
    // JNI library reads APK from disk and verifies against this certificate
    private static final byte[] ORIGINAL_CERT_BYTES = new byte[] {
        48, -126, 3, 84, 48, -126, 2, 60, 2, 1, 1, 48, 13, 6, 9, 42,
        -122, 72, -122, -9, 13, 1, 1, 11, 5, 0, 48, 112, 49, 23, 48, 21,
        6, 3, 85, 4, 3, 12, 14, 65, 118, 97, 110, 116, 105, 107, 97, 32,
        68, 111, 115, 104, 105, 49, 15, 48, 13, 6, 3, 85, 4, 11, 12, 6,
        83, 105, 110, 103, 108, 101, 49, 19, 48, 17, 6, 3, 85, 4, 10, 12,
        10, 73, 110, 100, 105, 118, 105, 100, 117, 97, 108, 49, 18, 48, 16, 6,
        3, 85, 4, 7, 12, 9, 78, 101, 119, 32, 68, 101, 108, 104, 105, 49,
        14, 48, 12, 6, 3, 85, 4, 8, 12, 5, 68, 101, 108, 104, 105, 49,
        11, 48, 9, 6, 3, 85, 4, 6, 19, 2, 57, 50, 48, 30, 23, 13,
        50, 52, 48, 57, 48, 52, 49, 57, 53, 53, 52, 51, 90, 23, 13, 52,
        57, 48, 56, 50, 57, 49, 57, 53, 53, 52, 51, 90, 48, 112, 49, 23,
        48, 21, 6, 3, 85, 4, 3, 12, 14, 65, 118, 97, 110, 116, 105, 107,
        97, 32, 68, 111, 115, 104, 105, 49, 15, 48, 13, 6, 3, 85, 4, 11,
        12, 6, 83, 105, 110, 103, 108, 101, 49, 19, 48, 17, 6, 3, 85, 4,
        10, 12, 10, 73, 110, 100, 105, 118, 105, 100, 117, 97, 108, 49, 18, 48,
        16, 6, 3, 85, 4, 7, 12, 9, 78, 101, 119, 32, 68, 101, 108, 104,
        105, 49, 14, 48, 12, 6, 3, 85, 4, 8, 12, 5, 68, 101, 108, 104,
        105, 49, 11, 48, 9, 6, 3, 85, 4, 6, 19, 2, 57, 50, 48, -126,
        1, 34, 48, 13, 6, 9, 42, -122, 72, -122, -9, 13, 1, 1, 1, 5,
        0, 3, -126, 1, 15, 0, 48, -126, 1, 10, 2, -126, 1, 1, 0, -106,
        85, -108, -39, 47, -11, 105, 126, 96, -57, 55, 40, -68, -10, 77, -80, 50,
        43, 94, 46, -2, -26, -86, -118, 90, -76, -38, 111, 27, 85, -18, -30, -84,
        -21, -99, 91, -77, -86, -64, -99, 56, 11, -52, 79, -15, -82, 83, -29, -56,
        -122, -117, -119, 19, -48, -46, 89, -103, -90, -58, -98, -122, -14, -78, -78, -27,
        -113, -117, -12, -34, 61, -10, -99, 29, -8, -105, -128, 101, 68, 42, -84, -99,
        -54, 74, -55, -50, -54, 92, 28, 124, -69, 125, 117, -81, -111, 25, -77, -12,
        -16, 67, 81, 15, 123, 55, 56, -4, 10, -85, 69, 115, -121, 81, 0, 71,
        3, 98, -95, -74, -82, -66, 84, 53, -1, -34, -33, -71, -41, 124, -68, 125,
        -106, -104, 99, 72, -82, -14, -73, 84, -88, 119, 43, 19, -40, -92, 102, 96,
        -104, -61, -66, 20, -84, 1, 30, -29, -14, 87, -126, 127, -80, -114, -1, 34,
        -13, -99, -66, 34, -45, 18, 9, -84, 0, -87, 65, 126, 93, -46, -81, -78,
        -52, -4, 126, 79, 87, 107, 40, 34, -79, -47, 95, 17, -93, 123, 58, -92,
        95, 127, 86, -69, 19, -66, -124, 68, -53, -15, -7, 12, 24, 118, -125, 123,
        105, -8, -38, 115, 3, -45, -29, -90, -87, 27, 55, 18, -59, 99, 103, -111,
        -62, 68, -74, 26, 42, 10, 119, -66, -82, -67, 26, 109, -88, -120, 106, 89,
        28, 117, -44, 40, 81, -115, -37, 119, 121, -58, 10, -69, 44, -105, 57, 2,
        3, 1, 0, 1, 48, 13, 6, 9, 42, -122, 72, -122, -9, 13, 1, 1,
        11, 5, 0, 3, -126, 1, 1, 0, 109, 76, 55, -16, 92, 19, 123, 113,
        -25, 19, 87, 79, 64, 17, -30, -111, -30, 7, -71, -96, -83, 65, -71, -22,
        87, -75, 90, -72, 101, -49, 9, 7, 123, 68, 67, -53, 52, -42, 5, -30,
        77, -103, 24, -43, -34, 15, 51, -23, 9, 113, -118, -50, -78, -36, -125, 81,
        42, -67, -61, 122, 114, -76, 48, 94, 13, -65, 11, -114, -50, -80, -97, -14,
        31, -102, 59, 26, 107, 118, -100, -30, -77, -92, -64, -37, -22, -21, 77, 5,
        -98, 57, -17, -49, 104, 42, 50, 90, 68, -43, 61, -60, 8, 10, 84, 7,
        65, 79, 51, -119, -114, -28, 122, -115, -29, -38, -80, -61, 115, 54, -60, 122,
        -76, 76, -93, 91, 104, 104, 37, -46, 80, -119, 23, -124, 56, -89, 43, -120,
        -4, 91, 104, -59, -64, -24, -78, -113, 94, 49, -1, -47, 32, 15, -107, 16,
        23, -95, -109, -73, 100, 106, -59, -21, -78, 35, 74, -29, 79, -38, -92, -105,
        65, -101, 123, -92, 32, 40, 91, 126, -127, -120, -109, 8, -21, 27, 89, 96,
        -10, 37, 62, -20, 15, 44, -86, -93, 78, -104, -97, -5, 20, -113, 107, -4,
        22, 85, 18, -117, 6, -103, 16, 27, -48, -76, 30, 121, -119, -11, -55, 75,
        -72, -126, -91, -74, 4, -84, -36, -92, -18, -21, -9, 46, -47, -11, -86, -56,
        94, 6, -121, -11, -55, 86, 2, -8, -4, 93, -14, 118, 28, 22, 112, -107,
        48, -35, -84, -114, 73, 100, -33, 116,
    };

    private static boolean isHookInstalled = false;
    private static Object originalIPackageManager = null;

    @Override
    public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
        String methodName = method.getName();
        System.out.println("IPackageManager method called: " + methodName + " args: " + java.util.Arrays.toString(args));
        
        if ("getPackageInfo".equals(methodName) && args.length >= 2) {
            String packageName = (String) args[0];
            if ("com.sportzx.live".equals(packageName)) {
                PackageInfo info = (PackageInfo) method.invoke(originalIPackageManager, args);
                if (info != null) {
                    Signature fakeSignature = new Signature(ORIGINAL_CERT_BYTES);
                    info.signatures = new Signature[] { fakeSignature };
                    
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                        try {
                            Class<?> signingDetailsClass = Class.forName("android.content.pm.SigningDetails");
                            java.lang.reflect.Constructor<?> signingDetailsConstructor = signingDetailsClass.getConstructor(Signature[].class, int.class);
                            Object signingDetails = signingDetailsConstructor.newInstance((Object) info.signatures, 1);
                            
                            Class<?> signingInfoClass = Class.forName("android.content.pm.SigningInfo");
                            java.lang.reflect.Constructor<?> signingInfoConstructor = signingInfoClass.getConstructor(signingDetailsClass);
                            Object signingInfo = signingInfoConstructor.newInstance(signingDetails);
                            
                            Field signingInfoField = PackageInfo.class.getField("signingInfo");
                            signingInfoField.setAccessible(true);
                            signingInfoField.set(info, signingInfo);
                        } catch (Exception e) {
                            System.out.println("Failed to mock signingInfo: " + e.getMessage());
                        }
                    }
                }
                return info;
            }
        }
        return method.invoke(originalIPackageManager, args);
    }

    public static synchronized void installSignatureHook() {
        if (isHookInstalled) return;
        try {
            System.out.println("Installing Signature Hook...");
            Class<?> activityThreadClass = Class.forName("android.app.ActivityThread");
            Method getPackageManagerMethod = activityThreadClass.getDeclaredMethod("getPackageManager");
            getPackageManagerMethod.setAccessible(true);
            originalIPackageManager = getPackageManagerMethod.invoke(null);

            if (originalIPackageManager == null) {
                System.out.println("Original IPackageManager is null!");
                return;
            }

            Class<?> iPackageManagerClass = Class.forName("android.content.pm.IPackageManager");
            Object proxyIPackageManager = Proxy.newProxyInstance(
                iPackageManagerClass.getClassLoader(),
                new Class<?>[] { iPackageManagerClass },
                new Decryptor()
            );

            Field sPackageManagerField = activityThreadClass.getDeclaredField("sPackageManager");
            sPackageManagerField.setAccessible(true);
            sPackageManagerField.set(null, proxyIPackageManager);

            isHookInstalled = true;
            System.out.println("Signature Hook installed successfully!");
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public static void main(String[] args) {
        try {
            System.out.println("Preparing Looper...");
            try {
                Looper.prepareMainLooper();
            } catch (Exception le) {
                // Already prepared or failed, continue
            }
            
            // Install the signature hook BEFORE loading the native library!
            installSignatureHook();
            
            System.out.println("Obtaining System Context...");
            Class<?> activityThreadClass = Class.forName("android.app.ActivityThread");
            Object activityThread = activityThreadClass.getMethod("systemMain").invoke(null);
            Context systemContext = (Context) activityThreadClass.getMethod("getSystemContext").invoke(activityThread);
            System.out.println("System context: " + systemContext);
            
            String packageName = (args.length >= 3) ? args[2] : "com.sportzx.live";
            System.out.println("Creating Package Context for " + packageName + "...");
            Context context = systemContext.createPackageContext(packageName, 
                Context.CONTEXT_INCLUDE_CODE | Context.CONTEXT_IGNORE_SECURITY);
            System.out.println("Package Context package name: " + context.getPackageName());
            
            // Load DataHelper class using Decryptor's classloader (CLASSPATH = Decryptor.jar + APK)
            // This finds our DataHelper STUB in Decryptor.jar; the JNI native methods will be
            // registered against this class when the native lib is loaded below.
            ClassLoader appClassLoader = Decryptor.class.getClassLoader();
            System.out.println("App ClassLoader: " + appClassLoader);
            Class<?> dataHelperClass = Class.forName("com.sportzx.live.helpers.DataHelper", true, appClassLoader);
            System.out.println("DataHelper class loaded: " + dataHelperClass);
            
            // NOW load the native library using Runtime - JNI_OnLoad will find DataHelper class
            System.out.println("Loading native-lib...");
            String libPath = args[0];
            // Load via Runtime with classLoader so JNI_OnLoad can register against app's DataHelper
            try {
                java.lang.reflect.Method runtimeLoad = Runtime.class.getDeclaredMethod("load0", Class.class, String.class);
                runtimeLoad.setAccessible(true);
                runtimeLoad.invoke(Runtime.getRuntime(), dataHelperClass, libPath);
            } catch (Exception ex) {
                // Fallback: regular System.load
                System.load(libPath);
            }
            System.out.println("Native-lib loaded successfully!");
            
            String encryptedData = args[1];
            if (encryptedData.startsWith("@")) {
                String filePath = encryptedData.substring(1);
                System.out.println("Reading encrypted payload from file: " + filePath);
                java.io.File file = new java.io.File(filePath);
                java.io.BufferedReader reader = new java.io.BufferedReader(new java.io.FileReader(file));
                StringBuilder sb = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) {
                    sb.append(line);
                }
                reader.close();
                encryptedData = sb.toString();
            }
            System.out.println("Data length to decrypt: " + encryptedData.length());
            
            Object instance = dataHelperClass.getField("INSTANCE").get(null);
            Method helpMethod = dataHelperClass.getMethod("help", Context.class, String.class);
            
            // Initialization call (mirrors be/p constructor behavior)
            String initToken = "3q2-7wZ1MCLV9YNJ0uDf2LSDrnLkU3g3UTlr";
            System.out.println("Calling init token on DataHelper.help...");
            String initResult = (String) helpMethod.invoke(instance, context, initToken);
            System.out.println("Init result length: " + (initResult != null ? initResult.length() : 0));
            
            // Iterative decryption: call help() until result is stable (or JSON found)
            // Some formats use double-stage: help(help(payload)) -> JSON
            String current = encryptedData;
            String previous = null;
            String finalResult = null;
            
            for (int stage = 1; stage <= 5; stage++) {
                System.out.println("Stage " + stage + " help() call, input length=" + current.length());
                String result = (String) helpMethod.invoke(instance, context, current);
                int resultLen = (result != null ? result.length() : 0);
                System.out.println("Stage " + stage + " result length: " + resultLen);
                
                if (result == null || result.length() == 0) {
                    System.out.println("Stage " + stage + ": empty result, stopping");
                    break;
                }
                
                // Check if result starts with [ or { (JSON)
                char firstChar = result.charAt(0);
                if (firstChar == '[' || firstChar == '{') {
                    System.out.println("Stage " + stage + ": RESULT IS JSON! (starts with " + firstChar + ")");
                    finalResult = result;
                    break;
                }
                
                // Check if result is same as input (passthrough = failed decryption)
                if (result.equals(current)) {
                    System.out.println("Stage " + stage + ": result == input (passthrough), stopping");
                    finalResult = result;
                    break;
                }
                
                previous = current;
                current = result;
                finalResult = result;
            }
            
            if (finalResult == null) finalResult = current;
            
            // ISO-8859-1 maps Java char code-point (0-255) 1:1 to bytes,
            // preserving ALL bytes including 0x00 (null) without truncation.
            byte[] rawBytes = finalResult.getBytes("ISO-8859-1");
            String b64 = android.util.Base64.encodeToString(rawBytes, android.util.Base64.NO_WRAP);
            System.out.println("DECRYPTION RESULT START");
            System.out.println(b64);
            System.out.println("DECRYPTION RESULT END");
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
