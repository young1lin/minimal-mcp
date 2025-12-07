package io.github.young1lin.server;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.logging.Logger;

import io.github.young1lin.tool.SimpleTool;
import io.github.young1lin.tool.annotation.Tool;
import io.github.young1lin.tool.annotation.ToolParam;

/**
 * 服务器会话类，包含工具方法
 */
public class ServerSession {

    private static final Logger logger = Logger.getLogger(ServerSession.class.getName());

    private final List<String> records = new ArrayList<>();

    public ServerSession() {
    }

    /**
     * Get the weather of a location
     *
     * @param location The location to get weather for, only support English Name of
     *                 the location, like "Beijing" or "Shanghai" or "Hangzhou"
     * @return The weather of the location
     */
    @Tool
    public String getWeather(
            @ToolParam(required = true, description = """
                    The location to get weather for, only support English Name of the location, like "Beijing" or "Shanghai" or "Hangzhou"
                    """) String location) {
        logger.info("get_weather called with location: " + location);
        records.add(location);

        if (location == null || location.isBlank()) {
            return "Location is required";
        }

        location = location.trim();

        String locationLower = location.toLowerCase();
        String result = switch (locationLower) {
            case "beijing" -> "The weather of Beijing is sunny, 25°C";
            case "shanghai" -> "The weather of Shanghai is cloudy, 22°C";
            case "hangzhou" -> "The weather of Hangzhou is rainy, 29°C, 80% humidity, wind 10km/h";
            case "nyc" -> "The weather of NYC is\n" +
                    "67°F°C\n" +
                    "Precipitation: 0%\n" +
                    "Humidity: 68%\n" +
                    "Wind: 6 mph";
            default -> "The weather of " + location + " is unspported, please try another location";
        };

        logger.info("get_weather returning: " + result);
        return result;
    }

    /**
     * List all get weather records
     */
    @Tool
    public List<String> listGetWeatherRecords() {
        logger.info("list_get_weather_records called, returning: " + records);
        return new ArrayList<>(records);
    }

    /**
     * 创建 getWeather 工具的 SimpleTool 对象
     */
    public SimpleTool getWeatherTool() {
        try {
            Method method = this.getClass().getMethod("getWeather", String.class);
            Map<String, Class<?>> arguments = new HashMap<>();
            arguments.put("location", String.class);
            List<String> requiredArguments = new ArrayList<>();
            requiredArguments.add("location");
            return new SimpleTool("get_weather", arguments,
                    "Get the weather of a location", requiredArguments, method, this);
        } catch (NoSuchMethodException e) {
            throw new RuntimeException(e);
        }
    }

    /**
     * 创建 listGetWeatherRecords 工具的 SimpleTool 对象
     */
    public SimpleTool listGetWeatherRecordsTool() {
        try {
            Method method = this.getClass().getMethod("listGetWeatherRecords");
            Map<String, Class<?>> arguments = new HashMap<>();
            List<String> requiredArguments = new ArrayList<>();
            return new SimpleTool("list_get_weather_records", arguments,
                    "List all get weather records", requiredArguments, method, this);
        } catch (NoSuchMethodException e) {
            throw new RuntimeException(e);
        }
    }

}
