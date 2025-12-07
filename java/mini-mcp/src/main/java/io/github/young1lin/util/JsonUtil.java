package io.github.young1lin.util;

import java.io.InputStream;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * JSON 工具类，使用 Jackson 库（Java 21 没有内置完整 JSON 库）
 */
public class JsonUtil {

    private static final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 将对象转换为 JSON 字符串
     */
    public static String toJson(Object obj) {
        if (obj == null) {
            return "null";
        }

        try {
            // 使用 Jackson 进行 JSON 序列化
            return objectMapper.writeValueAsString(obj);
        } catch (Exception e) {
            throw new RuntimeException("Failed to serialize object to JSON", e);
        }
    }

    /**
     * 将 JSON 字符串解析为 Map
     */
    public static Map<String, Object> parseJson(String json) {
        if (json == null || json.trim().isEmpty()) {
            return new HashMap<>();
        }

        try {
            // 使用 Jackson 进行 JSON 反序列化
            return objectMapper.readValue(json, new TypeReference<Map<String, Object>>() {
            });
        } catch (Exception e) {
            throw new RuntimeException("Failed to parse JSON string", e);
        }
    }

    public static <T> T convertValue(Object value, Class<T> clazz) {
        if (value == null) {
            return null;
        }

        try {
            return objectMapper.convertValue(value, clazz);
        } catch (Exception e) {
            throw new RuntimeException("Failed to convert value to " + clazz.getName(), e);
        }
    }

    /**
     * 将 inputstream 转成 Map<String, Object>
     */
    public static <T> Optional<T> parseJson(InputStream in, TypeReference<T> reference) {
        if (in == null) {
            return Optional.empty();
        }

        try {
            return Optional.ofNullable(objectMapper.readValue(in, reference));
        } catch (Exception e) {
            throw new RuntimeException("Failed to parse JSON inputstream", e);
        }
    }

    /**
     * 将 JSON 字符串解析为指定类型的对象
     */
    public static <T> T parseJson(String json, Class<T> clazz) {
        if (json == null || json.trim().isEmpty()) {
            return null;
        }

        try {
            return objectMapper.readValue(json, clazz);
        } catch (Exception e) {
            throw new RuntimeException("Failed to parse JSON string to " + clazz.getName(), e);
        }
    }
}
