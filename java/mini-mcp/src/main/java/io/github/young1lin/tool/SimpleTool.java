package io.github.young1lin.tool;

import java.lang.reflect.Method;
import java.util.List;
import java.util.Map;

public class SimpleTool implements Tool {

    private final String name;

    private final Map<String, Class<?>> arguments;

    private final String description;

    private final List<String> requiredArguments;

    private final Method func;

    /**
     * 用于存储方法所属的实例（如果有）
     */
    private final Object instance;

    public SimpleTool(String name, Map<String, Class<?>> arguments, String description,
            List<String> requiredArguments, Method func, Object instance) {
        this.name = name;
        this.arguments = arguments;
        this.description = description;
        this.requiredArguments = requiredArguments;
        this.func = func;
        this.instance = instance;
    }

    public String getName() {
        return name;
    }

    public Map<String, Class<?>> getArguments() {
        return arguments;
    }

    public String getDescription() {
        return description;
    }

    public java.util.List<String> getRequiredArguments() {
        return requiredArguments;
    }

    public Method getFunc() {
        return func;
    }

    public Object getInstance() {
        return instance;
    }

}
