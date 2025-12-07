package io.github.young1lin.tool.annotation;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;
import java.lang.annotation.Documented;

@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface Tool {
    
    String name() default "";

    String description() default "";
    
    boolean returnDirectly() default false;

    // maybe result is a image or file, we need to convert it to a url or file path
    // ToolCallResultConverter resultConverter();

}